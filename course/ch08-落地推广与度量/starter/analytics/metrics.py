"""指标：把事件流算成老板看得懂的四个数。

四类指标（缺一类，汇报就会被打回）：
  ① 使用（有没有人用）  活跃人数、使用天数、人均次数
  ② 效率（快了多少）    平均耗时、节省工时
  ③ 质量（对不对）      成功率、返工率
  ④ 成本（贵不贵）      单次成本、月成本

注意：**"使用率"和"效果"是两件事**。
用得少但效果好 = 推广问题；用得多但天天错 = 质量问题。要分开看。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .events import dedupe


def _day(ts: str) -> str:
    return ts[:10]


def _week(ts: str) -> str:
    d = datetime.strptime(ts[:10], "%Y-%m-%d").date()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def in_range(events: list[dict], start: str | None = None, end: str | None = None) -> list[dict]:
    out = []
    for e in dedupe(events):
        d = _day(e["ts"])
        if start and d < start:
            continue
        if end and d > end:
            continue
        out.append(e)
    return out


def summarize(events: list[dict]) -> dict:
    """一段区间内的核心指标。"""
    events = dedupe(events)
    if not events:
        return {"runs": 0, "users": 0, "days": 0, "success_rate": 0.0,
                "avg_duration_s": 0.0, "total_cost_cny": 0.0, "cost_per_run": 0.0,
                "runs_per_user": 0.0}

    users = {e["user"] for e in events}
    days = {_day(e["ts"]) for e in events}
    ok = sum(1 for e in events if e.get("ok"))
    total_dur = sum(float(e.get("duration_s") or 0) for e in events)
    total_cost = sum(float(e.get("cost_cny") or 0) for e in events)
    n = len(events)

    return {
        "runs": n,
        "users": len(users),
        "days": len(days),
        "success_rate": round(ok / n, 4),
        "avg_duration_s": round(total_dur / n, 2),
        "total_cost_cny": round(total_cost, 4),
        "cost_per_run": round(total_cost / n, 6),
        "runs_per_user": round(n / len(users), 2),
    }


def weekly_active(events: list[dict]) -> dict[str, int]:
    """每周活跃人数。看的是"有没有人持续回来用"。"""
    bucket: dict[str, set[str]] = defaultdict(set)
    for e in dedupe(events):
        bucket[_week(e["ts"])].add(e["user"])
    return {w: len(u) for w, u in sorted(bucket.items())}


def retention(events: list[dict], cohort_week: str, later_week: str) -> float:
    """留存：首批用的人里，后来还在用的比例。

    这是判断"工具是否真的进入工作流"最硬的指标。
    只看总次数会被少数重度用户掩盖。
    """
    events = dedupe(events)
    cohort = {e["user"] for e in events if _week(e["ts"]) == cohort_week}
    if not cohort:
        return 0.0
    later = {e["user"] for e in events if _week(e["ts"]) == later_week}
    return round(len(cohort & later) / len(cohort), 4)


def failure_reasons(events: list[dict], top: int = 5) -> list[tuple[str, int]]:
    """失败原因分布：决定你下一步该修什么。"""
    counts: dict[str, int] = defaultdict(int)
    for e in dedupe(events):
        if not e.get("ok"):
            counts[(e.get("error") or "unknown")] += 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:top]


def saved_hours(events: list[dict], manual_minutes: float) -> float:
    """节省工时 = 次数 ×（人工单次分钟 − 工具单次分钟）/ 60。

    关键假设必须写出来：manual_minutes 从哪来的？（访谈/计时/抽样）
    没有依据的"人工要 90 分钟"会在汇报时被当场质疑。
    """
    events = dedupe(events)
    if not events:
        return 0.0
    tool_minutes = sum(float(e.get("duration_s") or 0) for e in events) / 60
    manual_minutes_total = manual_minutes * len(events)
    return round(max(0.0, manual_minutes_total - tool_minutes) / 60, 2)
