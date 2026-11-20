"""CLI：埋点上报 / 区间报告 / 前后对比。

    python -m analytics.main log --user li --duration 4.2
    python -m analytics.main report --file data/events.jsonl
    python -m analytics.main compare --file data/events.jsonl \
        --before 2026-11-01 2026-11-07 --after 2026-11-08 2026-11-28 --manual-minutes 90
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import compare as cmp
from . import events as ev
from . import metrics as mt

ROOT = Path(__file__).resolve().parents[1]      # starter/
DEFAULT_FILE = ROOT / "data" / "events.jsonl"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="analytics", description="工具使用埋点与效果度量")
    sub = p.add_subparsers(dest="cmd", required=True)

    log = sub.add_parser("log", help="记录一条使用事件")
    log.add_argument("--user", required=True)
    log.add_argument("--tool", default="daily-report")
    log.add_argument("--action", default="run")
    log.add_argument("--duration", type=float, default=0.0)
    log.add_argument("--cost", type=float, default=0.0)
    log.add_argument("--fail", action="store_true")
    log.add_argument("--error", default="")
    log.add_argument("--file", default=str(DEFAULT_FILE))

    rep = sub.add_parser("report", help="区间报告")
    rep.add_argument("--file", default=str(DEFAULT_FILE))
    rep.add_argument("--start")
    rep.add_argument("--end")
    rep.add_argument("--manual-minutes", type=float, default=90.0)

    cmp_p = sub.add_parser("compare", help="前后对比")
    cmp_p.add_argument("--file", default=str(DEFAULT_FILE))
    cmp_p.add_argument("--before", nargs=2, metavar=("START", "END"), required=True)
    cmp_p.add_argument("--after", nargs=2, metavar=("START", "END"), required=True)
    cmp_p.add_argument("--manual-minutes", type=float, default=90.0)
    cmp_p.add_argument("--hourly-rate", type=float, default=90.0)
    cmp_p.add_argument("--out", help="把 markdown 写到文件")

    return p


def run(a) -> int:
    if a.cmd == "log":
        e = ev.make_event(a.user, a.tool, action=a.action, ok=not a.fail,
                          duration_s=a.duration, cost_cny=a.cost, error=a.error)
        n = ev.append_jsonl(a.file, [e])
        print(json.dumps({"written": n, "event": e}, ensure_ascii=False))
        return 0 if n == 1 else 1

    events = ev.load_jsonl(a.file)
    if a.cmd == "report":
        subset = mt.in_range(events, a.start, a.end)
        kpis = mt.summarize(subset)
        print(json.dumps({
            **kpis,
            "weekly_active": mt.weekly_active(subset),
            "saved_hours": mt.saved_hours(subset, a.manual_minutes),
            "failure_reasons": mt.failure_reasons(subset),
        }, ensure_ascii=False, indent=2))
        return 0

    before = mt.in_range(events, a.before[0], a.before[1])
    after = mt.in_range(events, a.after[0], a.after[1])
    result = cmp.compare(before, after, a.manual_minutes, a.hourly_rate)
    md = cmp.render_markdown(result)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        print(f"已写入 {a.out}")
    else:
        print(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
