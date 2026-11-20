"""CLI 入口（参考实现）。

退出码：0 成功 / 1 部分失败（产物可用）/ 2 致命失败（无产物）
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from .config import Config, load_config
from .report import render_anomalies_csv, render_daily_csv, render_markdown
from .transform import (
    build_daily_asin,
    compute_kpis,
    dedupe_by,
    find_anomalies,
    load_sources,
    reconcile,
)

log = logging.getLogger("pipeline")

# 缺了它就没法产出任何有意义结果的源
CRITICAL_FILES = {"business_report_us.csv"}


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


def resolve_range(start: str | None, end: str | None) -> tuple[str, str]:
    if start is None:
        start = (date.today() - timedelta(days=1)).isoformat()
    if end is None:
        end = start
    return start, end


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    file_handler = logging.FileHandler(
        log_dir / f"run-{date.today():%Y%m%d}.log", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream)


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def run(cfg: Config, start: str | None, end: str | None, dry_run: bool = False) -> int:
    try:
        start, end = resolve_range(start, end)
    except Exception:                                   # 理论上不会发生
        log.exception("日期解析失败")
        return 2
    if start > end:
        log.error("参数错误：start(%s) 晚于 end(%s)", start, end)
        return 2

    code = 0
    log.info("启动：start=%s end=%s dry_run=%s root=%s", start, end, dry_run, cfg.root)

    src = load_sources(cfg)
    if src.get("missing"):
        # 不是所有缺失都同级：主表缺失 = 无法产出，直接终止
        critical = [f for f in src["missing"] if f in CRITICAL_FILES]
        if critical:
            log.error("关键数据源缺失：%s，终止运行（不产出）", ", ".join(critical))
            return 2
        log.error("缺失数据源：%s（结果不完整）", ", ".join(src["missing"]))
        code = 1
    log.info("数据源行数：business=%d ads=%d settlement=%d erp=%d products=%d inventory=%d",
             len(src["business"]), len(src["ads"]), len(src["settlement"]),
             len(src["erp"]), len(src["products"]), len(src["inventory"]))

    raw_settlement = len(src["settlement"])
    settlement = dedupe_by(src["settlement"], "transaction_id")
    if raw_settlement != len(settlement):
        log.warning("结算去重：%d 行 → %d 行（去掉 %d 笔重复入账）",
                    raw_settlement, len(settlement), raw_settlement - len(settlement))

    rows = build_daily_asin(cfg, start, end, sources=src)
    n_asin = len({p["asin"] for p in src["products"]})
    n_dates = len({r["date"] for r in rows})
    expected = n_asin * n_dates
    if len(rows) != expected:
        log.error("宽表行数异常：%d，期望 %d（%d ASIN × %d 天）", len(rows), expected, n_asin, n_dates)
        code = 1
    log.info("宽表：%d 行（%d ASIN × %d 天）", len(rows), n_asin, n_dates)

    kpis = compute_kpis(rows)
    log.info("核心指标：销售额 %.2f / 订单 %d / 退款 %.2f / ACOS %s / TACOS %s",
             kpis["sales_usd"], kpis["units"], kpis["refund_usd"],
             kpis["acos"], kpis["tacos"])

    bridge = reconcile(rows, settlement)
    log.info("对账：净销售 %.2f → 计算净额 %.2f / 结算净额 %.2f / 残差 %.2f",
             bridge["net_sales"], bridge["computed_net"],
             bridge["settlement_net"], bridge["residual"])
    # 结算单是滚动账本（入账比下单晚 2 天），短区间必然不平。
    # 单日跑却报"对账失败"，只会训练业务忽略告警 —— 所以短区间跳过。
    try:
        period_days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        period_days = 0
    if period_days < 7:
        log.info("区间 %d 天 < 7 天，跳过多账残差校验（滚动账本，短区间必然不平）", period_days)
    elif abs(bridge["residual"]) > cfg.tolerance_usd:
        log.error("对账残差 %.2f 超过容差 %.2f", bridge["residual"], cfg.tolerance_usd)
        code = 1

    anomalies = find_anomalies(cfg, rows, src)
    level_of = {"ERROR": logging.ERROR, "WARN": logging.WARNING, "INFO": logging.INFO}
    for a in anomalies:
        log.log(level_of.get(a["severity"], logging.INFO),
                "[%s] %s | %s", a["type"], a["ref"], a["detail"])
    log.info("异常清单：%d 条", len(anomalies))

    if dry_run:
        log.info("dry-run：不产出文件，退出码 %d", code)
        return code

    _write_atomic(cfg.out_dir / "daily_asin.csv", render_daily_csv(rows))
    _write_atomic(cfg.out_dir / "anomalies.csv", render_anomalies_csv(anomalies))
    _write_atomic(cfg.out_dir / "report.md", render_markdown(kpis, bridge, anomalies, rows))
    log.info("产物已写入：%s", cfg.out_dir)
    return code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        print(f"配置文件不存在：{args.config}", file=sys.stderr)
        return 2
    except Exception as exc:                            # 配置写坏了也别崩
        print(f"配置解析失败：{exc}", file=sys.stderr)
        return 2
    setup_logging(cfg.log_dir)
    return run(cfg, args.start, args.end, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
