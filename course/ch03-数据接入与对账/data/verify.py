"""数据核对：算出第 3 章「对账报告」的参考答案（供出题时引用，学员勿看）。"""
import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")


def load(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


biz = load("business_report_us.csv")
stl = load("settlement_detail.csv")
erp = load("erp_orders.csv")
ads = load("ads_campaign_daily.csv")
st = load("ads_search_term_weekly.csv")
ret = load("returns.csv")
inv = load("inventory_snapshot.csv")
prod = load("products.csv")

f = lambda rows, k: sum(float(r[k]) for r in rows)

print("=" * 70)
print("【1】业务报告（站点时区，未扣退款）")
print("=" * 70)
print(f"销售额 ordered_product_sales_usd = {f(biz,'ordered_product_sales_usd'):,.2f}")
print(f"订单数 units_ordered               = {sum(int(r['units_ordered']) for r in biz):,}")
print(f"退款金额 refund_amount_usd         = {f(biz,'refund_amount_usd'):,.2f}")
print(f"退款件数 units_refunded            = {sum(int(r['units_refunded']) for r in biz):,}")
print(f"整体退款率 = {f(biz,'refund_amount_usd')/f(biz,'ordered_product_sales_usd')*100:.2f}%")

print("\n分 ASIN：")
by_asin = defaultdict(lambda: [0, 0.0, 0.0, 0])
for r in biz:
    a = by_asin[r["asin"]]
    a[0] += int(r["units_ordered"]); a[1] += float(r["ordered_product_sales_usd"])
    a[2] += float(r["refund_amount_usd"]); a[3] += int(r["units_refunded"])
for asin, (u, s, rf, ru) in sorted(by_asin.items()):
    print(f"  {asin}  单量 {u:>4}  销售 {s:>9,.2f}  退款 {rf:>8,.2f}  退款率 {rf/s*100:>5.2f}%")

print("\n" + "=" * 70)
print("【2】结算单（UTC）")
print("=" * 70)
print(f"交易总笔数 = {len(stl)}   净额合计 = {f(stl,'amount_usd'):,.2f}")
print(f"去重后笔数 = {len({r['transaction_id'] for r in stl})}  ← 差额即重复入账")
typ = defaultdict(lambda: [0, 0.0])
for r in stl:
    t = typ[r["transaction_type"]]
    t[0] += 1; t[1] += float(r["amount_usd"])
for k, (c, v) in sorted(typ.items()):
    print(f"  {k:<18} {c:>5} 笔   合计 {v:>12,.2f}")

print("\n按类型去重后：")
seen = set(); typ2 = defaultdict(lambda: [0, 0.0])
for r in stl:
    if r["transaction_id"] in seen:
        continue
    seen.add(r["transaction_id"])
    t = typ2[r["transaction_type"]]
    t[0] += 1; t[1] += float(r["amount_usd"])
for k, (c, v) in sorted(typ2.items()):
    print(f"  {k:<18} {c:>5} 笔   合计 {v:>12,.2f}")

print("\n佣金率反查（按 ASIN）：")
comm = defaultdict(float); sales = defaultdict(float)
for r in stl:
    if r["transaction_type"] == "Commission":
        comm[r["asin"]] += -float(r["amount_usd"])
for r in biz:
    sales[r["asin"]] += float(r["ordered_product_sales_usd"])
for asin in sorted(sales):
    cfg = next(p["commission_rate"] for p in prod if p["asin"] == asin)
    print(f"  {asin}  佣金额 {comm[asin]:>9,.2f}  销售额 {sales[asin]:>10,.2f}  "
          f"实际率 {comm[asin]/sales[asin]*100:>5.2f}%  配置 {float(cfg)*100:.0f}%")

print("\n" + "=" * 70)
print("【3】ERP 订单（北京时间）")
print("=" * 70)
print(f"总行数 = {len(erp)}")
oids = [r["order_id"] for r in erp]
print(f"唯一 order_id = {len(set(oids))}   重复行 = {len(erp) - len(set(oids))}")
st_cnt = defaultdict(int)
for r in erp:
    st_cnt[r["status"]] += 1
print("状态分布:", dict(st_cnt))
print(f"sku 为空的订单数 = {sum(1 for r in erp if not r['sku'].strip())}  ← 无法映射到 SKU")
print(f"ERP 名义件数(含取消/重复) = {sum(int(r['quantity']) for r in erp)}")
print(f"ERP 有效件数(去掉取消/重复) = "
      f"{sum(int(r['quantity']) for r in erp if r['status'] != 'cancelled') - (len(erp)-len(set(oids)))}")

def erp_by_date(convert):
    """按 ERP 有效订单汇总到日。convert=True 时把北京时间换算成站点日期。"""
    d_ = defaultdict(int)
    seen = set()
    for r in erp:
        if r["order_id"] in seen:
            continue
        seen.add(r["order_id"])
        if r["status"] == "cancelled":
            continue
        if convert:
            ts = datetime.strptime(r["purchase_date_bj"], "%Y-%m-%d %H:%M:%S")
            key = (ts - timedelta(hours=16)).date().isoformat()
        else:
            key = r["purchase_date_bj"][:10]
        d_[key] += int(r["quantity"])
    return d_


biz_by_date = defaultdict(int)
for r in biz:
    biz_by_date[r["report_date"]] += int(r["units_ordered"])

for convert, title in [(False, "未换算（直接拿北京日期）"), (True, "已换算（北京时间 -16h = 站点日期）")]:
    e_bd = erp_by_date(convert)
    dates = sorted(set(list(e_bd) + list(biz_by_date)))
    print(f"\n{title}：")
    print(f"  {'date':<12}{'ERP':>7}{'BIZ':>7}{'diff':>7}")
    for d in dates:
        e, b = e_bd.get(d, 0), biz_by_date.get(d, 0)
        if abs(e - b) > 25:
            print(f"  {d:<12}{e:>7}{b:>7}{e-b:>7}   <<<")
        elif d in ("2026-11-01", "2026-11-30", "2026-12-01"):
            print(f"  {d:<12}{e:>7}{b:>7}{e-b:>7}")
    total_diff = sum(e_bd.values()) - sum(biz_by_date.values())
    n_diff = sum(1 for d in dates if e_bd.get(d, 0) != biz_by_date.get(d, 0))
    print(f"  合计 {sum(e_bd.values())} vs {sum(biz_by_date.values())}，差异天数 {n_diff}，总差 {total_diff}")

print("\n" + "=" * 70)
print("【4】广告")
print("=" * 70)
print(f"广告总花费 = {f(ads,'spend_usd'):,.2f}   广告销售额 = {f(ads,'ad_sales_usd'):,.2f}")
print(f"整体 ACOS = {f(ads,'spend_usd')/f(ads,'ad_sales_usd')*100:.2f}%")
print(f"整体 TACOS = {f(ads,'spend_usd')/f(biz,'ordered_product_sales_usd')*100:.2f}%")
print("\n分 campaign：")
camp = defaultdict(lambda: [0.0, 0.0, 0, 0])
for r in ads:
    c = camp[r["campaign_name"]]
    c[0] += float(r["spend_usd"]); c[1] += float(r["ad_sales_usd"])
    c[2] += int(r["clicks"]); c[3] += int(r["ad_orders"])
for k, (s, sales_, clk, o) in sorted(camp.items()):
    print(f"  {k:<16} 花费 {s:>8,.2f}  广告销售额 {sales_:>9,.2f}  ACOS {s/sales_*100:>5.2f}%  "
          f"点击 {clk:>5}  广告 CVR {o/clk*100:>4.2f}%")

print("\n搜索词：高花费零转化 TOP")
for r in sorted(st, key=lambda x: -float(x["spend_usd"]))[:6]:
    print(f"  {r['week_start']}  {r['keyword']:<32} {r['match_type']:<7} "
          f"花费 {float(r['spend_usd']):>7,.2f}  单 {r['ad_orders']}")
print(f"搜索词报告总花费 = {f(st,'spend_usd'):,.2f}  （注意与 campaign 报表口径差异）")

print("\n" + "=" * 70)
print("【5】退货")
print("=" * 70)
print(f"退货笔数 = {len(ret)}  金额 = {f(ret,'refund_amount_usd'):,.2f}")
rc = defaultdict(int)
for r in ret:
    rc[r["reason"]] += 1
for k, v in sorted(rc.items(), key=lambda x: -x[1]):
    print(f"  {v:>3}  {k}")
ra = defaultdict(int)
for r in ret:
    ra[r["asin"]] += 1
print("按 ASIN:", dict(ra))

print("\n" + "=" * 70)
print("【6】库存")
print("=" * 70)
for r in inv:
    print(f"  {r['asin']}  可售 {r['available_qty']:>4}  在途 {r['inbound_qty']:>4}  "
          f"日均 {r['units_7d_avg']:>5}  DOI {r['doi']}")

print("\n" + "=" * 70)
print("【7】埋点异常自检")
print("=" * 70)
bad = [r for r in biz if int(r["units_ordered"]) == 0 and float(r["ordered_product_sales_usd"]) > 0]
print(f"  单量为 0 但销售额 > 0 的行数 = {len(bad)}  {[(r['report_date'], r['asin']) for r in bad]}")
dup_tx = len(stl) - len({r["transaction_id"] for r in stl})
print(f"  结算重复交易 = {dup_tx} 笔")
print(f"  退款总额(业务报告) {f(biz,'refund_amount_usd'):,.2f} vs "
      f"结算 Refund 行 {sum(-float(r['amount_usd']) for r in stl if r['transaction_type']=='Refund'):,.2f}")
nov_ads = sum(float(r["amount_usd"]) for r in stl
              if "Advertising" in r["description"] and r["posted_date_utc"].startswith("2026-11"))
dec_ads = sum(float(r["amount_usd"]) for r in stl
              if "Advertising" in r["description"] and r["posted_date_utc"].startswith("2026-12"))
print(f"  结算内广告费：11 月 {nov_ads:,.2f} / 12 月 {dec_ads:,.2f}（广告报表 11 月 {f(ads,'spend_usd'):,.2f}）")
