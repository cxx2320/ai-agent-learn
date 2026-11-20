"""渲染（参考实现）。只做「dict → 字符串」，不读文件、不算指标。"""

from __future__ import annotations

import csv
import io

ANOMALY_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}


def _money(v) -> str:
    return "—" if v is None else f"{v:,.2f}"


def _pct(v) -> str:
    return "—" if v is None else f"{v:.2%}"


def render_markdown(kpis: dict, bridge: dict, anomalies: list[dict], rows: list[dict]) -> str:
    dates = sorted({r["date"] for r in rows})
    span = f"{dates[0]} ~ {dates[-1]}" if dates else "—"
    lines: list[str] = []

    residual = bridge.get("residual")
    if residual is not None and abs(residual) > 0.01:
        lines.append(f"> ⚠️ 对账残差 {residual:.2f}，请核对口径后再使用本报告\n")

    lines.append("# 多站点日报\n")
    lines.append(f"- 数据区间：{span}")
    lines.append(f"- ASIN 数：{len({r['asin'] for r in rows})}")
    lines.append(f"- 明细行数：{len(rows)}\n")

    lines.append("## 核心指标\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---|")
    lines.append(f"| 销售额（未扣退款） | {_money(kpis.get('sales_usd'))} |")
    lines.append(f"| 订单数 | {kpis.get('units', 0):,} |")
    lines.append(f"| 退款金额 | {_money(kpis.get('refund_usd'))} |")
    lines.append(f"| 退款率 | {_pct(kpis.get('refund_rate'))} |")
    lines.append(f"| 广告花费 | {_money(kpis.get('ad_spend_usd'))} |")
    lines.append(f"| ACOS | {_pct(kpis.get('acos'))} |")
    lines.append(f"| TACOS | {_pct(kpis.get('tacos'))} |")
    lines.append(f"| 净收入（业务口径） | {_money(kpis.get('net_revenue_usd'))} |\n")

    lines.append("## 对账\n")
    lines.append("| 项目 | 金额 |")
    lines.append("|---|---|")
    lines.append(f"| 业务报告销售额 | {_money(bridge.get('sales_usd'))} |")
    lines.append(f"| − 业务报告退款 | {_money(bridge.get('refund_usd'))} |")
    lines.append(f"| = 净销售额 | {_money(bridge.get('net_sales'))} |")
    lines.append(f"| − 佣金 | {_money(bridge.get('commission_usd'))} |")
    lines.append(f"| − FBA 配送费 | {_money(bridge.get('fba_fee_usd'))} |")
    lines.append(f"| − 广告费 | {_money(bridge.get('ads_usd'))} |")
    lines.append(f"| − 仓储费 | {_money(bridge.get('storage_usd'))} |")
    lines.append(f"| + 退款时点差 | {_money(bridge.get('refund_timing_usd'))} |")
    lines.append(f"| = 计算净额 | {_money(bridge.get('computed_net'))} |")
    lines.append(f"| 结算单净额 | {_money(bridge.get('settlement_net'))} |")
    lines.append(f"| **残差** | **{0.0 if residual is None else residual:.2f}** |\n")

    lines.append("## 异常清单\n")
    if not anomalies:
        lines.append("无。\n")
    else:
        ordered = sorted(anomalies, key=lambda a: (ANOMALY_ORDER.get(a["severity"], 9), a["type"]))
        lines.append("| 级别 | 类型 | 对象 | 说明 |")
        lines.append("|---|---|---|---|")
        for a in ordered:
            lines.append(f"| {a['severity']} | {a['type']} | {a['ref']} | {a['detail']} |")
        lines.append("")

    return "\n".join(lines)


def render_daily_csv(rows: list[dict]) -> str:
    fields = ["date", "asin", "parent_asin", "sku", "sessions", "units",
              "sales_usd", "refund_usd", "ad_spend_usd", "ad_sales_usd",
              "commission_usd", "fba_fee_usd", "storage_fee_usd", "net_revenue_usd"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda x: (x["date"], x["asin"])):
        w.writerow({k: r.get(k) for k in fields})
    return buf.getvalue()


def render_anomalies_csv(anomalies: list[dict]) -> str:
    """异常清单 CSV。

    开头加 BOM（\ufeff）：Windows 上用 Excel 直接双击打开时，
    没有 BOM 的中文 CSV 会显示乱码。这是一个真实的交付细节——
    业务方不会去"用 UTF-8 导入"，他们只会双击。
    """
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["severity", "type", "ref", "detail"])
    for a in anomalies:
        w.writerow([a["severity"], a["type"], a["ref"], a["detail"]])
    return "\ufeff" + buf.getvalue()
