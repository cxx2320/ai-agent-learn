"""健康检查：定时任务上线后，第一个要有的东西不是监控大屏，是这个脚本。

它回答一个问题："今天这次运行，到底算成功吗？"

设计原则：
  1. 每项检查独立，一项失败不影响其余检查（要一次看全问题）
  2. 区分 WARN 与 CRITICAL —— 全都当致命会让人麻木
  3. 退出码就是给调度器/告警系统看的：0 正常 / 1 有警告 / 2 致命
  4. 输出既给人看（文本），也给机器看（--json）

用法：
    python -m ops.healthcheck --data-dir ../data/raw --out-dir ./output --date 2026-11-30
    python -m ops.healthcheck ... --json
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

OK, WARN, CRIT = "OK", "WARN", "CRIT"


@dataclass
class Result:
    name: str
    level: str
    detail: str


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, level: str, detail: str) -> None:
        self.results.append(Result(name, level, detail))

    @property
    def exit_code(self) -> int:
        levels = {r.level for r in self.results}
        if CRIT in levels:
            return 2
        if WARN in levels:
            return 1
        return 0

    def to_dict(self) -> dict:
        return {"exit_code": self.exit_code,
                "results": [r.__dict__ for r in self.results]}


def check_data_freshness(data_dir: Path, expect_date: str | None) -> Result:
    """数据新鲜度：业务报告里最新的日期，是否达到了期望日期。"""
    src = data_dir / "business_report_us.csv"
    if not src.exists():
        return Result("数据源存在", CRIT, f"找不到 {src}")
    with open(src, encoding="utf-8", newline="") as f:
        dates = sorted({r["report_date"] for r in csv.DictReader(f)})
    if not dates:
        return Result("数据源非空", CRIT, "业务报告没有任何数据行")
    latest = dates[-1]
    if expect_date and latest < expect_date:
        return Result("数据新鲜度", CRIT, f"最新数据 {latest}，期望不早于 {expect_date}")
    return Result("数据新鲜度", OK, f"最新数据 {latest}（共 {len(dates)} 天）")


def check_outputs(out_dir: Path, max_age_hours: float | None) -> list[Result]:
    """产物是否齐全、非空、够新。"""
    out: list[Result] = []
    for name, min_bytes in (("daily_asin.csv", 200), ("report.md", 200)):
        p = out_dir / name
        if not p.exists():
            out.append(Result(f"产物 {name}", CRIT, "文件不存在"))
            continue
        size = p.stat().st_size
        if size < min_bytes:
            out.append(Result(f"产物 {name}", CRIT, f"文件过小（{size} 字节），疑似空产出"))
            continue
        if max_age_hours is not None:
            age_h = (datetime.now().timestamp() - p.stat().st_mtime) / 3600
            if age_h > max_age_hours:
                out.append(Result(f"产物 {name}", CRIT,
                                  f"已 {age_h:.1f} 小时未更新（上限 {max_age_hours} 小时）"))
                continue
        out.append(Result(f"产物 {name}", OK, f"{size} 字节"))
    return out


def check_reconcile(out_dir: Path, tolerance: float) -> Result:
    """对账残差：直接读 report.md 里的残差行。"""
    p = out_dir / "report.md"
    if not p.exists():
        return Result("对账残差", WARN, "报告不存在，跳过残差检查")
    text = p.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "残差" in line:
            digits = "".join(ch if (ch.isdigit() or ch in ".-") else " " for ch in line)
            nums = [x for x in digits.split() if x not in ("", "-", ".", "--")]
            try:
                residual = abs(float(nums[-1]))
            except (IndexError, ValueError):
                return Result("对账残差", WARN, f"无法解析残差行：{line.strip()}")
            if residual > tolerance:
                return Result("对账残差", CRIT, f"残差 {residual:.2f} 超过容差 {tolerance:.2f}")
            return Result("对账残差", OK, f"残差 {residual:.2f} 在容差内")
    return Result("对账残差", WARN, "报告里没有找到残差行")


def check_disk(path: Path, min_free_gb: float) -> Result:
    free_gb = shutil.disk_usage(path).free / 1024 ** 3
    if free_gb < min_free_gb:
        return Result("磁盘空间", CRIT, f"剩余 {free_gb:.1f} GB，低于 {min_free_gb} GB")
    return Result("磁盘空间", OK, f"剩余 {free_gb:.1f} GB")


def run(data_dir: Path, out_dir: Path, expect_date: str | None,
        max_age_hours: float | None, tolerance: float, min_free_gb: float) -> Report:
    rep = Report()
    rep.results.append(check_data_freshness(data_dir, expect_date))
    rep.results.extend(check_outputs(out_dir, max_age_hours))
    rep.results.append(check_reconcile(out_dir, tolerance))
    rep.results.append(check_disk(out_dir if out_dir.exists() else Path.cwd(), min_free_gb))
    return rep


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="healthcheck", description="日报管道健康检查")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--date", help="期望的数据最新日期 YYYY-MM-DD")
    p.add_argument("--max-age-hours", type=float, default=30)
    p.add_argument("--tolerance", type=float, default=1.0)
    p.add_argument("--min-free-gb", type=float, default=1.0)
    p.add_argument("--skip-reconcile", action="store_true",
                   help="跳过对账残差检查。单日运行时必须加：结算单是滚动账本，"
                        "单日必然不平，检查它只会制造假警报")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    rep = run(Path(a.data_dir), Path(a.out_dir), a.date,
              a.max_age_hours, a.tolerance, a.min_free_gb)
    if a.skip_reconcile:
        rep.results = [r for r in rep.results if r.name != "对账残差"]

    if a.json:
        print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"健康检查 @ {datetime.now():%Y-%m-%d %H:%M}")
        for r in rep.results:
            print(f"  [{r.level:<4}] {r.name:<14} {r.detail}")
        print(f"\n退出码 = {rep.exit_code}（0 正常 / 1 警告 / 2 致命）")
    return rep.exit_code


if __name__ == "__main__":
    sys.exit(main())
