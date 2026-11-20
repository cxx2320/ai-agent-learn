"""把 data/raw/*.csv 加载进 SQLite，生成 crossborder.db。

用法：
    python load.py

说明：
- 全部字段按 TEXT 落库，数值列额外提供 CAST 用法的示例（见文件末尾 SQL 示例）。
  真实项目里应该显式定义类型，这里为了让「格式化出错」这类问题暴露出来，
  故意不对 CSV 做任何清洗 —— 这正是第 3 章的练习内容。
"""

import csv
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw")
DB = os.path.join(BASE, "crossborder.db")

TABLES = {
    "products": "asin, parent_asin, sku, title_cn, category, price_usd, commission_rate, unit_cost_cny, first_launch_date",
    "fx_rate": "rate_date, usd_cny",
    "business_report": "report_date, asin, sessions, page_views, units_ordered, ordered_product_sales_usd, units_refunded, refund_amount_usd, buy_box_pct",
    "ads_campaign": "report_date, campaign_name, asin, impressions, clicks, spend_usd, ad_sales_usd, ad_orders",
    "ads_search_term": "week_start, week_end, campaign_name, keyword, match_type, impressions, clicks, spend_usd, ad_sales_usd, ad_orders",
    "erp_orders": "order_id, purchase_date_bj, sku, asin, quantity, amount_cny, status, channel",
    "settlement": "transaction_id, posted_date_utc, settlement_id, transaction_type, order_id, asin, sku, quantity, amount_usd, description",
    "returns": "return_date, order_id, asin, quantity, reason, refund_amount_usd",
    "inventory": "snapshot_date, asin, sku, available_qty, inbound_qty, reserved_qty, units_7d_avg, doi",
}

FILES = {
    "products": "products.csv",
    "fx_rate": "fx_rate.csv",
    "business_report": "business_report_us.csv",
    "ads_campaign": "ads_campaign_daily.csv",
    "ads_search_term": "ads_search_term_weekly.csv",
    "erp_orders": "erp_orders.csv",
    "settlement": "settlement_detail.csv",
    "returns": "returns.csv",
    "inventory": "inventory_snapshot.csv",
}

if os.path.exists(DB):
    os.remove(DB)

conn = sqlite3.connect(DB)
cur = conn.cursor()

for table, cols in TABLES.items():
    col_defs = ", ".join(f'"{c.strip()}" TEXT' for c in cols.split(","))
    cur.execute(f'CREATE TABLE "{table}" (row_id INTEGER PRIMARY KEY, {col_defs})')
    path = os.path.join(RAW, FILES[table])
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        sql = f'INSERT INTO "{table}" ({cols}) VALUES ({",".join("?" * len(header))})'
        cur.executemany(sql, [r for r in reader])
    n = cur.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print(f"  {table:<16} {n:>6} rows")

conn.commit()
conn.close()
print(f"\n已生成：{DB}")
print("""
试试这几条（注意数值是 TEXT，算数要 CAST）：
  SELECT COUNT(*), SUM(CAST(ordered_product_sales_usd AS REAL)) FROM business_report;
  SELECT transaction_type, COUNT(*), ROUND(SUM(CAST(amount_usd AS REAL)),2)
    FROM settlement GROUP BY transaction_type;
  SELECT status, COUNT(*) FROM erp_orders GROUP BY status;
""")
