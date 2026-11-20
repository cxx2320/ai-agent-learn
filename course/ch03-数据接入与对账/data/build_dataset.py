"""
生成第 3 章练习用的「跨境电商模拟数据集」。

设计目标：
1. 字段名、时区、口径尽量贴近真实后台导出的报表；
2. 三方数据（业务报告 / 结算单 / ERP）**可以用 order_id 逐单对上**，
   但对不上时一定有个真实原因（取消、重复、时区、退款时点、佣金率）；
3. 数据量适中（约 6000 行），SQL 能查得动；
4. 固定随机种子，可复现。

用法：python build_dataset.py
输出：./raw/*.csv
"""

import csv
import os
import random
from datetime import date, datetime, time, timedelta

random.seed(20261119)

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)

START, END = date(2026, 11, 1), date(2026, 11, 30)
DAYS = [START + timedelta(days=i) for i in range((END - START).days + 1)]
FX = 7.12

PRODUCTS = [
    # asin, parent, sku, title, category, price, commission_rate, unit_cost_cny, base_units, launch
    ("B0C1AAA1", "B0C1PARA", "WR-CHARGE-BLK", "无线充电支架 黑色", "Cell Phones Accessories", 29.99, 0.15, 82, 12, "2025-03-11"),
    ("B0C1AAA2", "B0C1PARA", "WR-CHARGE-WHT", "无线充电支架 白色", "Cell Phones Accessories", 29.99, 0.15, 82, 8, "2025-03-11"),
    ("B0C1AAA3", "B0C1PARA", "WR-CHARGE-BLU", "无线充电支架 蓝色", "Cell Phones Accessories", 31.99, 0.15, 85, 3, "2025-09-02"),
    ("B0C1BBB1", "B0C1PARB", "ORG-BOX-GRY", "桌面收纳盒 灰", "Home & Kitchen", 19.99, 0.15, 41, 15, "2025-06-20"),
    ("B0C1BBB2", "B0C1PARB", "ORG-BOX-BLK", "桌面收纳盒 黑", "Home & Kitchen", 19.99, 0.15, 41, 10, "2025-06-20"),
    ("B0C1BBB3", "B0C1PARB", "", "桌面收纳盒 粉", "Home & Kitchen", 18.99, 0.15, 39, 5, "2026-02-14"),
]
# ↑ BBB3 的 sku 为空 —— 埋点：SKU 映射缺失，订单无法映射到商品

FBA_FEE = {"B0C1AAA1": 5.20, "B0C1AAA2": 5.20, "B0C1AAA3": 5.20,
           "B0C1BBB1": 4.10, "B0C1BBB2": 4.10, "B0C1BBB3": 4.10}

ACTUAL_COMMISSION = {p[0]: p[6] for p in PRODUCTS}
ACTUAL_COMMISSION["B0C1BBB1"] = 0.17   # 埋点：实际佣金 17%，配置是 15%

CAMPAIGNS = [
    ("SP-Auto-WR", "B0C1AAA1", 26.0, 0.62, 0.24),
    ("SP-Manual-WR", "B0C1AAA2", 12.0, 0.75, 0.31),
    ("SP-Auto-ORG", "B0C1BBB1", 14.0, 0.48, 0.55),   # 效率最差
    ("SB-Brand-ORG", "B0C1PARB", 9.0, 0.90, 0.28),
]

DAY_FACTOR = {date(2026, 11, 26): 1.6, date(2026, 11, 27): 3.2, date(2026, 11, 28): 2.6,
              date(2026, 11, 29): 2.0, date(2026, 11, 30): 2.2}

RETURN_REASONS = ["Item defective or doesn't work", "No longer needed", "Bought by mistake",
                  "Item arrived damaged", "Missing parts or accessories",
                  "Product didn't match description", "Wrong item was sent", "Unauthorized purchase"]


def write_csv(name, header, rows):
    with open(os.path.join(RAW, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {name:<32} {len(rows):>6} rows")


def price_on(d, base_price):
    return round(base_price * 0.88, 2) if d >= date(2026, 11, 27) else base_price


# ============================================================ 0. 先生成订单真值
# 一个 order = 一个订单行，quantity 恒为 1（简化）
orders = []   # dict: order_id, report_date, asin, price, status, bj_date
seq = 0
for d in DAYS:
    for asin, _p, sku, _t, _c, price, _cr, _cost, base, _l in PRODUCTS:
        f = DAY_FACTOR.get(d, 1.0) * (1.15 if d.weekday() >= 5 else 1.0) * random.uniform(0.85, 1.15)
        units = max(0, int(round(base * f)))
        for _ in range(units):
            seq += 1
            cancelled = random.random() < 0.03
            status = "cancelled" if cancelled else ("pending" if random.random() < 0.01 else "shipped")
            # 埋点：ERP 存北京时间。真实时刻 = 站点当天随机小时 + 16h（PST→北京）
            t = random.uniform(0, 24)
            bj_dt = datetime.combine(d, time(0, 0)) + timedelta(hours=t + 16)
            orders.append({
                "order_id": f"112-{d.strftime('%y%m%d')}-{seq:06d}",
                "report_date": d, "asin": asin, "price": price_on(d, price),
                "status": status, "bj_ts": bj_dt.strftime("%Y-%m-%d %H:%M:%S"),
            })

valid = [o for o in orders if o["status"] != "cancelled"]

# ============================================================ 1. 主数据
write_csv("products.csv",
          ["asin", "parent_asin", "sku", "title_cn", "category", "price_usd",
           "commission_rate", "unit_cost_cny", "first_launch_date"],
          [(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[9]) for p in PRODUCTS])

write_csv("fx_rate.csv", ["rate_date", "usd_cny"], [(d.isoformat(), FX) for d in DAYS])

# ============================================================ 2. 业务报告（站点时区）
business_rows = []
for d in DAYS:
    for asin, _p, _sku, _t, _c, price, _cr, _cost, _base, _l in PRODUCTS:
        day_orders = [o for o in valid if o["report_date"] == d and o["asin"] == asin]
        units = len(day_orders)
        price_today = price_on(d, price)
        sales = round(units * price_today, 2)

        refund_rate = 0.11 if asin == "B0C1BBB2" else random.uniform(0.02, 0.05)
        units_refunded = sum(1 for _ in day_orders if random.random() < refund_rate)
        refund_amount = round(units_refunded * price_today, 2)

        sessions = int(round(units / random.uniform(0.09, 0.14))) + random.randint(0, 12)
        if units and sessions == 0:
            sessions = units * 8
        business_rows.append([d.isoformat(), asin, sessions,
                              int(sessions * random.uniform(1.2, 1.8)), units, sales,
                              units_refunded, refund_amount, round(random.uniform(88, 99), 1)])

# 埋点 A：sessions=0 但 units>0（转化率无法计算，清洗时要处理）
# 埋点 B：buy_box_pct 为空（缺失值）
for r in business_rows:
    if r[0] == "2026-11-12" and r[1] == "B0C1AAA2" and r[4] > 0:
        r[2] = 0
        r[3] = 0
    if r[0] in ("2026-11-19", "2026-11-20") and r[1] == "B0C1BBB2":
        r[8] = ""

write_csv("business_report_us.csv",
          ["report_date", "asin", "sessions", "page_views", "units_ordered",
           "ordered_product_sales_usd", "units_refunded", "refund_amount_usd", "buy_box_pct"],
          business_rows)

# ============================================================ 3. 广告 campaign 日报
campaign_rows = []
for d in DAYS:
    f = DAY_FACTOR.get(d, 1.0) * (1.2 if d.weekday() >= 5 else 1.0)
    for name, asin, base_spend, cpc, acos in CAMPAIGNS:
        spend = round(base_spend * f * random.uniform(0.85, 1.15), 2)
        clicks = max(1, int(round(spend / cpc)))
        ad_sales = round(spend / acos * random.uniform(0.9, 1.1), 2)
        aov = 29.99 if asin.startswith("B0C1AAA") else 19.99
        campaign_rows.append([d.isoformat(), name, asin, clicks * random.randint(90, 150),
                              clicks, spend, ad_sales, max(0, int(round(ad_sales / aov)))])
write_csv("ads_campaign_daily.csv",
          ["report_date", "campaign_name", "asin", "impressions", "clicks",
           "spend_usd", "ad_sales_usd", "ad_orders"], campaign_rows)

# ============================================================ 4. 搜索词周报（花费占用 campaign 的比例）
WEEKS = [("2026-11-01", "2026-11-07"), ("2026-11-08", "2026-11-14"),
         ("2026-11-15", "2026-11-21"), ("2026-11-22", "2026-11-30")]
KEYWORDS = [("wireless charger stand", "exact"), ("phone stand", "broad"),
            ("desk organizer", "broad"), ("charging station", "phrase"),
            ("iphone charger stand", "exact"), ("office desk organizer", "phrase"),
            ("charger holder", "broad"), ("cell phone stand for desk", "exact"),
            ("cable organizer box", "broad"), ("desk accessories", "broad"),
            ("wireless charging pad", "phrase"), ("3 in 1 charging stand", "exact"),
            ("tablet stand", "broad"), ("pen holder", "broad"), ("desk storage", "phrase"),
            ("charging dock", "broad")]
# 埋点 C：三个「高花费零转化」的词，是广告诊断的核心素材
BAD = {"2026-11-08": ("wireless charger", "broad", 120.00),
       "2026-11-15": ("phone stand cheap", "broad", 95.00),
       "2026-11-22": ("charging cable organizer", "broad", 110.00)}

search_rows = []
for ws, we in WEEKS:
    wd = date.fromisoformat(ws)
    week_spend = sum(float(r[5]) for r in
                     [c for c in campaign_rows
                      if c[1] == "SP-Auto-WR" and ws <= c[0] <= we])
    bad = BAD.get(ws)
    bad_spend = 0.0
    if bad:
        kw, mt, bad_spend = bad
        clicks = int(round(bad_spend / 0.58))
        search_rows.append([ws, we, "SP-Auto-WR", kw, mt, clicks * 130, clicks,
                            round(bad_spend, 2), 0.0, 0])
    remain = max(0.0, week_spend * 0.90 - bad_spend)
    weights = [random.uniform(0.5, 1.5) for _ in KEYWORDS]
    total_w = sum(weights)
    for (kw, mt), w in zip(KEYWORDS, weights):
        spend = round(remain * w / total_w, 2)
        clicks = max(1, int(round(spend / random.uniform(0.5, 0.9))))
        orders_n = sum(1 for _ in range(clicks) if random.random() < random.uniform(0.02, 0.09))
        sales = round(orders_n * random.uniform(19, 32), 2) if orders_n else 0.0
        search_rows.append([ws, we, "SP-Auto-WR", kw, mt, clicks * random.randint(100, 150),
                            clicks, spend, sales, orders_n])
write_csv("ads_search_term_weekly.csv",
          ["week_start", "week_end", "campaign_name", "keyword", "match_type",
           "impressions", "clicks", "spend_usd", "ad_sales_usd", "ad_orders"], search_rows)

# ============================================================ 5. ERP 订单（北京时间）
erp_rows = []
for o in orders:
    sku = next(p[2] for p in PRODUCTS if p[0] == o["asin"])
    erp_rows.append([o["order_id"], o["bj_ts"], sku, o["asin"],
                     1, round(o["price"] * FX, 2), o["status"], "Amazon-US"])
# 埋点 D：7 笔订单被重复抓取（同一 order_id 出现两次）
for idx in [17, 233, 501, 900, 1402, 1888, 1950]:
    if idx < len(erp_rows):
        erp_rows.append(list(erp_rows[idx]))
random.shuffle(erp_rows)
write_csv("erp_orders.csv",
          ["order_id", "purchase_date_bj", "sku", "asin", "quantity",
           "amount_cny", "status", "channel"], erp_rows)

# ============================================================ 6. 结算单（UTC）
settle_rows, return_records = [], []
settle_seq = 0


def add_settle(posted, ttype, order_id, asin, sku, amount, desc):
    global settle_seq
    settle_seq += 1
    settle_rows.append([f"TX{settle_seq:07d}", posted, f"S{posted[:7].replace('-', '')}",
                        ttype, order_id, asin, sku, 1, round(amount, 2), desc])


refund_by_order = {}
for o in valid:
    d, asin, price = o["report_date"], o["asin"], o["price"]
    sku = next(p[2] for p in PRODUCTS if p[0] == asin)
    posted = (d + timedelta(days=2)).isoformat()
    add_settle(posted, "ProductSales", o["order_id"], asin, sku, price, "Order Payment")
    add_settle(posted, "Commission", o["order_id"], asin, sku,
               -round(price * ACTUAL_COMMISSION[asin], 2),
               f"Commission {ACTUAL_COMMISSION[asin]*100:.0f}%")
    add_settle(posted, "FBAFulfillmentFee", o["order_id"], asin, sku,
               -FBA_FEE[asin], "FBA Fulfillment Fee")

# 退款：按「退款发生日」入账（落后下单日 7-20 天）—— 埋点 E：退款时点与业务报告错位
for r in business_rows:
    d, asin, n_ref = date.fromisoformat(r[0]), r[1], int(r[6])
    for k in range(n_ref):
        rdate = d + timedelta(days=random.randint(7, 20))
        amount = round(float(r[5]) / int(r[4]) if int(r[4]) else 0, 2)
        sku = next(p[2] for p in PRODUCTS if p[0] == asin)
        if rdate <= END:          # 只入账 11 月内发生的退款，12 月的下期才结算
            add_settle(rdate.isoformat(), "Refund", f"REF-{d.strftime('%y%m%d')}-{asin[-4:]}{k}",
                       asin, sku, -amount, "Refund principal")
            return_records.append([rdate.isoformat(), f"REF-{d.strftime('%y%m%d')}-{asin[-4:]}{k}",
                                   asin, 1, random.choice(RETURN_REASONS), amount])

# 广告费：按 UTC 落账（+1 天）—— 埋点 F：11-30 的广告费落到 12-01
for r in campaign_rows:
    d = date.fromisoformat(r[0])
    add_settle((d + timedelta(days=1)).isoformat(), "ServiceFee", "", "",
               "", -float(r[5]), f"Cost of Advertising - {r[1]}")

# 月度仓储费
for asin, fee in [("B0C1AAA1", 21.40), ("B0C1AAA2", 13.80), ("B0C1AAA3", 4.90),
                  ("B0C1BBB1", 26.10), ("B0C1BBB2", 17.30), ("B0C1BBB3", 8.20)]:
    add_settle("2026-11-30", "ServiceFee", "", asin, "", -fee, "FBA Monthly Storage Fee")

# 埋点 G：2 笔重复入账
for row in [settle_rows[10], settle_rows[3000]]:
    settle_rows.append(list(row))

random.shuffle(settle_rows)
write_csv("settlement_detail.csv",
          ["transaction_id", "posted_date_utc", "settlement_id", "transaction_type",
           "order_id", "asin", "sku", "quantity", "amount_usd", "description"], settle_rows)

write_csv("returns.csv",
          ["return_date", "order_id", "asin", "quantity", "reason", "refund_amount_usd"],
          return_records)

# ============================================================ 7. 库存快照
inv_rows = []
for asin, _p, sku, _t, _c, _pr, _cr, _c2, _b, _l in PRODUCTS:
    last7 = [r for r in business_rows if r[1] == asin and r[0] >= "2026-11-24"]
    avg = sum(int(r[4]) for r in last7) / max(1, len(last7))
    available = random.randint(60, 260)
    inv_rows.append(["2026-11-30", asin, sku, available, random.randint(0, 180),
                     random.randint(0, 40), round(avg, 1),
                     round(available / avg, 1) if avg else ""])
write_csv("inventory_snapshot.csv",
          ["snapshot_date", "asin", "sku", "available_qty", "inbound_qty",
           "reserved_qty", "units_7d_avg", "doi"], inv_rows)

print(f"\n完成。订单 {len(orders)} 笔（有效 {len(valid)}），数据目录：{RAW}")
