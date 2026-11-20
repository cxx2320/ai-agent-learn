"""第 7 章的入口：把运维件串起来。

    python run.py                          # 列出可用命令
    python run.py check                    # 健康检查（默认指向第 3 章数据 + 第 4 章产物）
    python run.py alert --title "测试"      # 告警 dry-run

真正的定时执行请用 deploy/run_daily.ps1（它会同时跑管道 + 检查 + 告警）。
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ops import healthcheck, notify   # noqa: E402

DEFAULT_DATA = ROOT.parents[1] / "ch03-数据接入与对账" / "data" / "raw"
DEFAULT_OUT = ROOT.parents[1] / "ch04-Python数据管道" / "solution" / "output"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run", description="运维件入口")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("check", help="健康检查")
    c.add_argument("--data-dir", default=str(DEFAULT_DATA))
    c.add_argument("--out-dir", default=str(DEFAULT_OUT))
    c.add_argument("--date")
    c.add_argument("--json", action="store_true")
    c.add_argument("--skip-reconcile", action="store_true")

    a = sub.add_parser("alert", help="告警（默认 dry-run）")
    a.add_argument("--title", required=True)
    a.add_argument("--line", action="append", default=[])
    a.add_argument("--severity", default="error", choices=list(notify.SEVERITY_PREFIX))
    a.add_argument("--send", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "check":
        extra = ["--json"] if args.json else []
        if args.skip_reconcile:
            extra.append("--skip-reconcile")
        if args.date:
            extra += ["--date", args.date]
        return healthcheck.main(["--data-dir", args.data_dir, "--out-dir", args.out_dir, *extra])
    if args.cmd == "alert":
        extra = ["--send"] if args.send else []
        return notify.main(["--title", args.title, "--severity", args.severity,
                            *sum([["--line", x] for x in args.line], []), *extra])

    print(__doc__)
    print(f"默认数据目录：{DEFAULT_DATA}")
    print(f"默认产物目录：{DEFAULT_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
