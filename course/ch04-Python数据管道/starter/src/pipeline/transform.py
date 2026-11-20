"""纯函数层：清洗、汇总、指标、对账、异常。

规矩：这个文件里不许出现 open()/Path.read_text()。所有 IO 由 load_sources 统一负责，
其余函数只吃 list[dict]、只吐 list[dict]/dict —— 这样才测得动。

行（row）统一用 dict，字段名与 CSV 表头一致，数值已经转成 float/int。
"""

from __future__ import annotations

from datetime import datetime, timedelta

# ---------------------------------------------------------------- 契约常量
REQUIRED_BUSINESS = {
    "report_date", "asin", "sessions", "units_ordered",
    "ordered_product_sales_usd", "units_refunded", "refund_amount_usd",
}
REQUIRED_ADS = {"report_date", "campaign_name", "asin", "spend_usd", "ad_sales_usd"}
REQUIRED_SETTLEMENT = {"transaction_id", "posted_date_utc", "transaction_type", "amount_usd"}

# 黄金数字（第 3 章人工核对出来的，回归测试就靠它）
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


# ---------------------------------------------------------------- IO（唯一允许读文件的地方）
def read_csv(path) -> list[dict]:
    """读 CSV → list[dict]。空字符串保留为 ''（不要擅自转成 0，那是清洗阶段的事）。"""
    raise NotImplementedError("TODO: read_csv")


def load_sources(cfg) -> dict:
    """读 5 个数据源，返回 {'business': [...], 'ads': [...], 'settlement': [...],
    'erp': [...], 'products': [...]}。

    要求：
      - 用 REQUIRED_* 做列校验，缺列要抛 ValueError（带文件名和缺的列名）
      - 单个文件不存在时**不要崩**：记到返回值的 'missing' 里，其余继续
        返回形如 {'business': [...], ..., 'missing': ['business_report_us.csv']}
    """
    raise NotImplementedError("TODO: load_sources")


# ---------------------------------------------------------------- 清洗
def site_date_from_bj(ts: str, offset_hours: int = -16) -> str:
    """北京时间字符串 → 站点日期字符串。

    >>> site_date_from_bj("2026-12-01 02:00:00") == "2026-11-30"
    >>> site_date_from_bj("2026-11-15 20:00:00") == "2026-11-15"

    实现提示：datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") + timedelta(hours=offset_hours)
    """
    raise NotImplementedError("TODO: site_date_from_bj")


def dedupe_by(rows: list[dict], key: str) -> list[dict]:
    """按业务主键去重，保留第一次出现的行，顺序不变。

    用例：dedupe_by(settlement, "transaction_id") —— 本数据集能去掉 2 笔重复入账。
    """
    raise NotImplementedError("TODO: dedupe_by")


# ---------------------------------------------------------------- 汇总
def build_daily_asin(cfg, start: str | None = None, end: str | None = None) -> list[dict]:
    """构建「日 × ASIN」宽表。

    输出每行至少包含：
        date, asin, sessions, units, sales_usd, refund_usd,
        ad_spend_usd, ad_sales_usd, commission_usd, fba_fee_usd,
        storage_fee_usd, net_revenue_usd

    硬要求（测试会查）：
      1. 11 月全量 = 180 行（6 ASIN × 30 天），0 单的日子也要有行
      2. Σsales_usd = 46322.64；Σad_spend_usd = 2362.54
      3. 广告必须**先聚合再连接**，否则行数会翻倍
      4. 父体广告（campaign 挂在父 ASIN 上）要摊到子体，否则这笔钱会丢
      5. 佣金/配送费要归到「下单日」（用 erp 的 order_id 关联），
         不能归到结算单的 posted_date（那是入账日，晚 2 天，跨月就丢）

    提示：business 决定行集；其余 LEFT JOIN 进去。
    """
    raise NotImplementedError("TODO: build_daily_asin")


def compute_kpis(rows: list[dict]) -> dict:
    """从宽表算总指标。

    返回键（tests 依赖）：sales_usd, units, refund_usd, refund_rate,
                        ad_spend_usd, ad_sales_usd, acos, tacos, net_revenue_usd
    注意 acos/tacos 的分母为 0 时返回 None，不要抛 ZeroDivisionError。
    """
    raise NotImplementedError("TODO: compute_kpis")


# ---------------------------------------------------------------- 对账
def reconcile(rows: list[dict], settlement_rows: list[dict]) -> dict:
    """生成对账桥。

    返回（tests 依赖）：
      {
        "sales_usd": ..., "refund_usd": ..., "net_sales": ...,
        "commission_usd": ..., "fba_fee_usd": ..., "ads_usd": ...,
        "storage_usd": ..., "refund_timing_usd": ...,
        "settlement_net": ..., "computed_net": ..., "residual": ...
      }

    computed_net = net_sales - 佣金 - 配送费 - 广告 - 仓储 + refund_timing
    residual     = settlement_net - computed_net
    正确实现下 residual 应为 0.00。
    """
    raise NotImplementedError("TODO: reconcile")


# ---------------------------------------------------------------- 异常
def find_anomalies(cfg, rows: list[dict], sources: dict) -> list[dict]:
    """扫出异常，返回 list[dict]，每行至少 {type, ref, detail, severity}。

    至少覆盖这 6 类（severity 用 INFO/WARN/ERROR）：
      sessions_zero          有订单但 sessions=0
      missing_buybox_share   buy_box_pct 为空
      unmapped_sku           erp 里 sku 为空
      duplicate_transaction  结算重复入账
      high_refund_rate       分 ASIN 退款率超阈值
      low_doi                库存 DOI 低于阈值
    """
    raise NotImplementedError("TODO: find_anomalies")
