"""只读校验：在内存库中跑答案里的宽表 SQL，确认能跑通且数字对得上。"""
import os
import pathlib
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "crossborder.db")

conn = sqlite3.connect(pathlib.Path(DB).as_uri() + "?mode=ro", uri=True)
conn.execute("PRAGMA temp_store = MEMORY")
conn.execute("ATTACH DATABASE ':memory:' AS w")

SQL = """
CREATE TABLE w.dwd_daily_asin AS
WITH biz AS (
    SELECT report_date AS date_site, asin,
           CAST(sessions AS INTEGER) AS sessions,
           CAST(units_ordered AS INTEGER) AS units_ordered,
           CAST(ordered_product_sales_usd AS REAL) AS sales_usd,
           CAST(refund_amount_usd AS REAL) AS refund_usd,
           buy_box_pct
    FROM business_report
),
prod AS (SELECT asin, parent_asin, COALESCE(sku,'') AS sku FROM products),
ads_raw AS (
    SELECT report_date AS date_site, asin,
           SUM(CAST(spend_usd AS REAL)) AS sp,
           SUM(CAST(ad_sales_usd AS REAL)) AS sa
    FROM ads_campaign GROUP BY 1,2
),
ads AS (
    SELECT date_site, asin,
           SUM(ad_spend_usd) AS ad_spend_usd,
           SUM(ad_sales_usd) AS ad_sales_usd
    FROM (
        SELECT a.date_site,
               CASE WHEN p.asin IS NULL THEN c.asin ELSE a.asin END AS asin,
               a.sp / CASE WHEN p.asin IS NULL
                           THEN (SELECT COUNT(*) FROM products x WHERE x.parent_asin = a.asin)
                           ELSE 1 END AS ad_spend_usd,
               a.sa / CASE WHEN p.asin IS NULL
                           THEN (SELECT COUNT(*) FROM products x WHERE x.parent_asin = a.asin)
                           ELSE 1 END AS ad_sales_usd
        FROM ads_raw a
        LEFT JOIN products p ON p.asin = a.asin
        LEFT JOIN products c ON c.parent_asin = a.asin
    )
    GROUP BY 1,2
),
order_fee AS (
    SELECT e.site_date, e.asin,
           SUM(CASE WHEN s.transaction_type='Commission' THEN -CAST(s.amount_usd AS REAL) ELSE 0 END) AS commission_usd,
           SUM(CASE WHEN s.transaction_type='FBAFulfillmentFee' THEN -CAST(s.amount_usd AS REAL) ELSE 0 END) AS fba_fee_usd
    FROM (SELECT DISTINCT order_id, asin, date(purchase_date_bj,'-16 hours') AS site_date
            FROM erp_orders WHERE status <> 'cancelled') e
    JOIN (SELECT * FROM settlement GROUP BY transaction_id) s ON e.order_id = s.order_id
    WHERE s.transaction_type IN ('Commission','FBAFulfillmentFee')
    GROUP BY 1,2
),
storage AS (
    SELECT asin, SUM(-CAST(amount_usd AS REAL)) AS storage_usd
    FROM (SELECT * FROM settlement GROUP BY transaction_id)
    WHERE transaction_type='ServiceFee' AND description LIKE '%Storage%'
    GROUP BY 1
)
SELECT b.date_site, b.asin, p.parent_asin, p.sku,
       b.sessions, b.units_ordered, b.sales_usd, b.refund_usd,
       COALESCE(a.ad_spend_usd,0) AS ad_spend_usd,
       COALESCE(a.ad_sales_usd,0) AS ad_sales_usd,
       COALESCE(ROUND(f.commission_usd,2),0) AS commission_usd,
       COALESCE(ROUND(f.fba_fee_usd,2),0) AS fba_fee_usd,
       CASE WHEN b.date_site='2026-11-30' THEN COALESCE(ROUND(s.storage_usd,2),0) ELSE 0 END AS storage_fee_usd,
       b.sales_usd - b.refund_usd
             - COALESCE(f.commission_usd,0) - COALESCE(f.fba_fee_usd,0)
             - COALESCE(a.ad_spend_usd,0)
             - CASE WHEN b.date_site='2026-11-30' THEN COALESCE(s.storage_usd,0) ELSE 0 END AS net_revenue_usd,
       CASE WHEN b.sessions = 0 THEN 'sessions_zero'
            WHEN b.buy_box_pct IS NULL OR TRIM(b.buy_box_pct)='' THEN 'missing_buybox'
            ELSE '' END AS data_flags
FROM biz b
LEFT JOIN prod      p ON p.asin = b.asin
LEFT JOIN ads       a ON a.asin = b.asin AND a.date_site = b.date_site
LEFT JOIN order_fee f ON f.asin = b.asin AND f.site_date = b.date_site
LEFT JOIN storage   s ON s.asin = b.asin;
"""

conn.executescript(SQL)

checks = [
    ("行数（应为 180）", "SELECT COUNT(*) FROM w.dwd_daily_asin"),
    ("SUM(sales)（应为 46322.64）", "SELECT ROUND(SUM(sales_usd),2) FROM w.dwd_daily_asin"),
    ("SUM(ad_spend)（应为 2362.54）", "SELECT ROUND(SUM(ad_spend_usd),2) FROM w.dwd_daily_asin"),
    ("SUM(commission)（应为 7165.92）", "SELECT ROUND(SUM(commission_usd),2) FROM w.dwd_daily_asin"),
    ("SUM(fba)（应为 8999.50）", "SELECT ROUND(SUM(fba_fee_usd),2) FROM w.dwd_daily_asin"),
    ("SUM(storage)（应为 91.70）", "SELECT ROUND(SUM(storage_fee_usd),2) FROM w.dwd_daily_asin"),
    ("SUM(net_revenue)", "SELECT ROUND(SUM(net_revenue_usd),2) FROM w.dwd_daily_asin"),
    ("每个 ASIN 行数（应全为 30）",
     "SELECT GROUP_CONCAT(c) FROM (SELECT COUNT(*) c FROM w.dwd_daily_asin GROUP BY asin)"),
    ("flags 分布",
     "SELECT data_flags, COUNT(*) FROM w.dwd_daily_asin GROUP BY data_flags"),
    ("net_revenue 是否对上对账桥 26541.49",
     "SELECT ROUND(SUM(net_revenue_usd) - 26541.49, 2) FROM w.dwd_daily_asin"),
]
for label, q in checks:
    print(f"  {label:<34} {conn.execute(q).fetchall()}")
