"""前后对比：上线前 vs 上线后。这是你唯一能拿出的"效果证据"。

三个必须守的规矩：
  1. **同口径**：前后都用同一套算法、同一个时间窗长度
  2. **写清基线**：人工单次耗时怎么来的（访谈/抽查/工时记录）
  3. **区分因果与相关**：同时上线了两个工具，就别把功劳全算自己头上
"""

from __future__ import annotations

from . import metrics


def compare(before: list[dict], after: list[dict], manual_minutes: float,
            hourly_rate: float = 90.0) -> dict:
    """返回可写进汇报的对比结果。"""
    b = metrics.summarize(before)
    a = metrics.summarize(after)

    saved_b = metrics.saved_hours(before, manual_minutes)
    saved_a = metrics.saved_hours(after, manual_minutes)
    money = round(saved_a * hourly_rate, 2)

    return {
        "before": b,
        "after": a,
        "manual_minutes": manual_minutes,
        "hourly_rate": hourly_rate,
        "saved_hours_before": saved_b,
        "saved_hours_after": saved_a,
        "saved_money_cny": money,
        "cost_cny": a["total_cost_cny"],
        "net_benefit_cny": round(money - a["total_cost_cny"], 2),
        "quality_delta": round(a["success_rate"] - b["success_rate"], 4),
        "duration_delta_s": round(a["avg_duration_s"] - b["avg_duration_s"], 2),
    }


def render_markdown(result: dict, tool: str = "daily-report") -> str:
    b, a = result["before"], result["after"]
    lines = [
        f"# 效果复盘：{tool}",
        "",
        "## 一句话结论",
        "",
        f"上线后累计运行 {a['runs']} 次，"
        f"节省约 {result['saved_hours_after']:.1f} 小时，"
        f"折合 {result['saved_money_cny']:,.0f} 元，"
        f"工具成本 {result['cost_cny']:.2f} 元。",
        "",
        "## 使用情况",
        "",
        "| 指标 | 上线前 | 上线后 |",
        "|---|---|---|",
        f"| 运行次数 | {b['runs']} | {a['runs']} |",
        f"| 使用人数 | {b['users']} | {a['users']} |",
        f"| 覆盖天数 | {b['days']} | {a['days']} |",
        f"| 人均次数 | {b['runs_per_user']} | {a['runs_per_user']} |",
        "",
        "## 效率与质量",
        "",
        "| 指标 | 上线前 | 上线后 | 变化 |",
        "|---|---|---|---|",
        f"| 成功率 | {b['success_rate']:.2%} | {a['success_rate']:.2%} | {result['quality_delta']:+.2%} |",
        f"| 平均耗时(秒) | {b['avg_duration_s']:.1f} | {a['avg_duration_s']:.1f} | {result['duration_delta_s']:+.1f} |",
        f"| 单次成本(元) | {b['cost_per_run']:.4f} | {a['cost_per_run']:.4f} | — |",
        "",
        "## 价值换算",
        "",
        f"- 人工基线：每次 {result['manual_minutes']:.0f} 分钟（来源需注明：访谈/抽查/工时记录）",
        f"- 节省工时：{result['saved_hours_after']:.1f} 小时",
        f"- 折合金额：{result['saved_money_cny']:,.0f} 元（时薪 {result['hourly_rate']:.0f} 元）",
        f"- 净收益：{result['net_benefit_cny']:,.0f} 元",
        "",
        "> ⚠️ 以上为过程指标。**业务结果**（少亏的钱、多赚的毛利）需单独取证，不能直接等同。",
    ]
    return "\n".join(lines) + "\n"
