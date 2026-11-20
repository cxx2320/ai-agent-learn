"""CLI 入口：参数 → 日志 → 编排 → 产物 → 退出码。

退出码约定：
    0 全部成功
    1 部分失败（有异常清单，产物可用）
    2 致命失败（无产物）
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from .config import Config, load_config

log = logging.getLogger("pipeline")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pipeline",
        description="多站点日报管道：读报表 → 清洗 → 宽表 → 对账 → 日报",
    )
    p.add_argument("--config", default="config/settings.yaml", help="配置文件路径")
    p.add_argument("--start", help="开始日期 YYYY-MM-DD，默认昨天")
    p.add_argument("--end", help="结束日期 YYYY-MM-DD（含），默认与 --start 相同")
    p.add_argument("--dry-run", action="store_true", help="只校验不产出")
    return p


def setup_logging(log_dir: Path) -> None:
    """控制台 + 文件双写。文件按天切分：run-YYYYMMDD.log

    要求：文件用 utf-8；格式含 时间/级别/模块/消息；
         日志级别 INFO（--verbose 再开 DEBUG，这个可以后加）。
    """
    raise NotImplementedError("TODO: setup_logging")


def run(cfg: Config, start: str | None, end: str | None, dry_run: bool = False) -> int:
    """主流程。返回退出码。

    步骤（顺序很重要）：
      1. 解析日期范围（默认昨天）；start > end 直接报错返回 2
      2. load_sources，检查有没有 missing 的数据源 → 有就记 ERROR 并记入清单
      3. build_daily_asin → 校验行数（11 月全量应 180 行，不符记 ERROR）
      4. compute_kpis
      5. reconcile → 残差超容差记 ERROR，退出码降为 1
      6. find_anomalies
      7. dry_run 则到此为止，只打日志
      8. 产出：
           output/daily_asin.csv      原子写（先 .tmp 再 os.replace）
           output/report.md
           output/anomalies.csv
      9. 返回退出码
    """
    raise NotImplementedError("TODO: run")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        print(f"配置文件不存在：{args.config}", file=sys.stderr)
        return 2
    setup_logging(cfg.log_dir)
    return run(cfg, args.start, args.end, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
