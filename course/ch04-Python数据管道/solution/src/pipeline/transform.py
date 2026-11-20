"""纯函数层（参考实现）。

设计要点：
  1. 除 load_sources / read_csv 外，所有函数都不碰文件；
  2. 金额一律 float（教学场景够用，生产建议用整数分或 Decimal）；
  3. 分组聚合统一用 dict，不引入第三方库。
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REQUIRED_BUSINESS = {
    "report_date", "asin", "sessions", "units_ordered",
    "ordered_product_sales_usd", "units_refunded", "refund_amount_usd",
}
REQUIRED_ADS = {"report_date", "campaign_name", "asin", "spend_usd", "ad_sales_usd"}
REQUIRED_SETTLEMENT = {"transaction_id", "posted_date_utc", "transaction_type", "amount_usd"}
REQUIRED_ERP = {"order_id", "purchase_date_bj", "asin", "sku", "status"}
REQUIRED_PRODUCTS = {"asin", "parent_asin", "sku"}
REQUIRED_INVENTORY = {"asin", "available_qty", "units_7d_avg", "doi"}

FILES = {
    "business": "business_report_us.csv",
    "ads": "ads_campaign_daily.csv",
    "settlement": "settlement_detail.csv",
    "erp": "erp_orders.csv",
    "products": "products.csv",
    "inventory": "inventory_snapshot.csv",
}
REQUIRED = {
    "business": REQUIRED_BUSINESS,
    "ads": REQUIRED_ADS,
    "settlement": REQUIRED_SETTLEMENT,
    "erp": REQUIRED_ERP,
    "products": REQUIRED_PRODUCTS,
    "inventory": REQUIRED_INVENTORY,
}

GOLDEN = {
    "sales_usd": 46322.64,
    "units": 1964,
    "refund_usd": 2306.31,
    "ad_spend_usd": 2362.54,
    "ad_sales_usd": 7985.89,
    "commission_usd": 7165.92,
    "fba_fee_usd": 8999.50,
    "storage_fee_usd": 91.70,
    "settlement_net": 26541.49,
}


def _f(v, default: float = 0.0) -> float:
    """宽松转 float：空串 / None / 脏值都当 0，绝不抛异常。"""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("$", "")
    if s == "":
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _i(v, default: int = 0) -> int:
    try:
        return int(round(_f(v, default)))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- IO
def read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_sources(cfg) -> dict:
    out: dict = {"missing": []}
    for key, filename in FILES.items():
        p = Path(cfg.data_dir) / filename
        if not p.exists():
            out["missing"].append(filename)
            out[key] = []
            continue
        rows = read_csv(p)
        cols = set(rows[0].keys()) if rows else set()
        lack = REQUIRED[key] - cols
        if lack:
            raise ValueError(f"{filename} 缺列：{sorted(lack)}")
        out[key] = rows
    return out


# ---------------------------------------------------------------- 清洗
def site_date_from_bj(ts: str, offset_hours: int = -16) -> str:
    """北京时间 → 站点日期。offset=-16 即 UTC+8 → UTC-8。"""
    dt = datetime.strptime(ts.strip()[:19], "%Y-%m-%d %H:%M:%S")
    return (dt + timedelta(hours=offset_hours)).date().isoformat()


def dedupe_by(rows: list[dict], key: str) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        k = r.get(key)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


# ---------------------------------------------------------------- 汇总
def _in_range(d: str, start: str | None, end: str | None) -> bool:
    if start and d < start:
        return False
    if end and d > end:
        return False
    return True


def build_daily_asin(cfg, start: str | None = None, end: str | None = None,
                     sources: dict | None = None) -> list[dict]:
    src = sources or load_sources(cfg)
    offset = cfg.site_offset_from_bj_hours

    # 1) 商品主数据
    parent_of = {p["asin"]: p["parent_asin"] for p in src["products"]}
    sku_of = {p["asin"]: (p["sku"] or "") for p in src["products"]}
    children_of: dict[str, list[str]] = defaultdict(list)
    for asin, parent in parent_of.items():
        children_of[parent].append(asin)

    # 2) 业务报告打底
    biz: dict[tuple[str, str], dict] = {}
    for r in src["business"]:
        d, asin = r["report_date"], r["asin"]
        if not _in_range(d, start, end):
            continue
        biz[(d, asin)] = {
            "date": d, "asin": asin,
            "sessions": _i(r["sessions"]),
            "units": _i(r["units_ordered"]),
            "sales_usd": _f(r["ordered_product_sales_usd"]),
            "refund_usd": _f(r["refund_amount_usd"]),
            "buy_box_pct": r.get("buy_box_pct", ""),
        }

    # 3) 广告：先聚合到 日×ASIN，父体摊到子体，再聚合一次（关键！）
    ads_raw: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in src["ads"]:
        d = r["report_date"]
        if not _in_range(d, start, end):
            continue
        acc = ads_raw[(d, r["asin"])]
        acc[0] += _f(r["spend_usd"])
        acc[1] += _f(r["ad_sales_usd"])

    ads: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for (d, asin), (spend, sales) in ads_raw.items():
        kids = children_of.get(asin)
        if kids:                                  # 这个 ASIN 是父体 → 平摊到子体
            share = 1.0 / len(kids)
            for kid in kids:
                ads[(d, kid)][0] += spend * share
                ads[(d, kid)][1] += sales * share
        else:                                     # 普通子体
            ads[(d, asin)][0] += spend
            ads[(d, asin)][1] += sales

    # 4) 结算：佣金/配送费回到「下单日」
    order_date: dict[str, tuple[str, str]] = {}
    seen_orders = set()
    for r in src["erp"]:
        oid = r["order_id"]
        if oid in seen_orders:
            continue
        seen_orders.add(oid)
        if (r.get("status") or "").lower() == "cancelled":
            continue
        order_date[oid] = (site_date_from_bj(r["purchase_date_bj"], offset), r["asin"])

    fees: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    storage: dict[str, float] = defaultdict(float)
    settlement = dedupe_by(src["settlement"], "transaction_id")

    for r in settlement:
        ttype = r["transaction_type"]
        amount = _f(r["amount_usd"])
        if ttype == "Commission":
            key = order_date.get(r["order_id"])
            if key:
                fees[key][0] += -amount
        elif ttype == "FBAFulfillmentFee":
            key = order_date.get(r["order_id"])
            if key:
                fees[key][1] += -amount
        elif ttype == "ServiceFee" and "Storage" in (r.get("description") or ""):
            storage[r["asin"]] += -amount

    storage_date = None
    for r in settlement:
        if r["transaction_type"] == "ServiceFee" and "Storage" in (r.get("description") or ""):
            storage_date = r["posted_date_utc"][:10]
            break

    # 5) 组装
    out: list[dict] = []
    for (d, asin), b in sorted(biz.items()):
        fee = fees.get((d, asin), [0.0, 0.0])
        ad = ads.get((d, asin), [0.0, 0.0])
        st = storage.get(asin, 0.0) if (storage_date and d == storage_date) else 0.0
        net = b["sales_usd"] - b["refund_usd"] - fee[0] - fee[1] - ad[0] - st
        out.append({
            "date": d,
            "asin": asin,
            "parent_asin": parent_of.get(asin, ""),
            "sku": sku_of.get(asin, ""),
            "sessions": b["sessions"],
            "units": b["units"],
            "sales_usd": round(b["sales_usd"], 2),
            "refund_usd": round(b["refund_usd"], 2),
            "ad_spend_usd": round(ad[0], 4),
            "ad_sales_usd": round(ad[1], 4),
            "commission_usd": round(fee[0], 2),
            "fba_fee_usd": round(fee[1], 2),
            "storage_fee_usd": round(st, 2),
            "net_revenue_usd": round(net, 4),
            "buy_box_pct": b["buy_box_pct"],
        })
    return out


def compute_kpis(rows: list[dict]) -> dict:
    sales = sum(r["sales_usd"] for r in rows)
    refund = sum(r["refund_usd"] for r in rows)
    units = sum(r["units"] for r in rows)
    ad_spend = sum(r["ad_spend_usd"] for r in rows)
    ad_sales = sum(r["ad_sales_usd"] for r in rows)
    net = sum(r["net_revenue_usd"] for r in rows)
    return {
        "sales_usd": round(sales, 2),
        "units": units,
        "refund_usd": round(refund, 2),
        "refund_rate": round(refund / sales, 4) if sales else None,
        "ad_spend_usd": round(ad_spend, 2),
        "ad_sales_usd": round(ad_sales, 2),
        "acos": round(ad_spend / ad_sales, 4) if ad_sales else None,
        "tacos": round(ad_spend / sales, 4) if sales else None,
        "net_revenue_usd": round(net, 2),
    }


def reconcile(rows: list[dict], settlement_rows: list[dict]) -> dict:
    sales = sum(r["sales_usd"] for r in rows)
    refund = sum(r["refund_usd"] for r in rows)
    commission = sum(r["commission_usd"] for r in rows)
    fba = sum(r["fba_fee_usd"] for r in rows)
    ads = sum(r["ad_spend_usd"] for r in rows)
    storage = sum(r["storage_fee_usd"] for r in rows)

    refund_posted = sum(-_f(r["amount_usd"]) for r in settlement_rows
                        if r["transaction_type"] == "Refund")
    settlement_net = sum(_f(r["amount_usd"]) for r in settlement_rows)

    net_sales = sales - refund
    refund_timing = refund - refund_posted
    computed = net_sales - commission - fba - ads - storage + refund_timing

    return {
        "sales_usd": round(sales, 2),
        "refund_usd": round(refund, 2),
        "net_sales": round(net_sales, 2),
        "commission_usd": round(commission, 2),
        "fba_fee_usd": round(fba, 2),
        "ads_usd": round(ads, 2),
        "storage_usd": round(storage, 2),
        "refund_posted_usd": round(refund_posted, 2),
        "refund_timing_usd": round(refund_timing, 2),
        "settlement_net": round(settlement_net, 2),
        "computed_net": round(computed, 2),
        "residual": round(settlement_net - computed, 2),
    }


def find_anomalies(cfg, rows: list[dict], sources: dict) -> list[dict]:
    th = cfg.thresholds
    out: list[dict] = []

    def add(severity, atype, ref, detail):
        out.append({"severity": severity, "type": atype, "ref": ref, "detail": detail})

    for f in sources.get("missing", []):
        add("ERROR", "missing_source", f, "数据源文件不存在，本次结果不完整")

    for r in rows:
        if r["sessions"] == 0 and r["units"] > 0:
            add("WARN", "sessions_zero", f'{r["date"]}/{r["asin"]}',
                f'sessions=0 但有 {r["units"]} 单，CVR 无法计算')
        if (r["buy_box_pct"] or "").strip() == "":
            add("INFO", "missing_buybox_share", f'{r["date"]}/{r["asin"]}', "buy_box_pct 缺失")

    empty_sku = [r for r in sources.get("erp", []) if not (r.get("sku") or "").strip()]
    if empty_sku:
        asins = sorted({r["asin"] for r in empty_sku})
        add("WARN", "unmapped_sku", ",".join(asins),
            f"{len(empty_sku)} 行 erp 订单 sku 为空，无法映射到商品")

    raw = len(sources.get("settlement", []))
    deduped = len(dedupe_by(sources.get("settlement", []), "transaction_id"))
    if raw > deduped:
        add("ERROR", "duplicate_transaction", "settlement", f"{raw - deduped} 笔重复入账，已去重")

    by_asin: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        by_asin[r["asin"]][0] += r["sales_usd"]
        by_asin[r["asin"]][1] += r["refund_usd"]
    for asin, (s, rf) in sorted(by_asin.items()):
        if s and rf / s > th["refund_rate_warn"]:
            add("WARN", "high_refund_rate", asin, f"退款率 {rf / s:.2%} 超过阈值 {th['refund_rate_warn']:.0%}")

    for r in sources.get("inventory", []):
        doi = _f(r.get("doi"), -1)
        if 0 <= doi < th["doi_warn"]:
            add("WARN", "low_doi", r["asin"],
                f"DOI {doi:.1f} 天低于阈值 {th['doi_warn']} 天，有断货风险")

    return out
