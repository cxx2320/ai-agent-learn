"""CLI：批量生成 + 评估 + 落盘。

    python run.py --mock                # 不联网，先跑通全链路
    python run.py --real --limit 3      # 调真模型，先看 3 条
    python run.py --real --resume       # 断点续跑

退出码：0 全部成功 / 1 有失败样本但仍产出 / 2 致命（缺 Key、缺模板）
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger("listing")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="listing", description="Listing 批量生成器")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="用本地假模型（不联网）")
    mode.add_argument("--real", action="store_true", help="调用真实模型")
    p.add_argument("--limit", type=int, default=0, help="只跑前 N 条，0 表示全部")
    p.add_argument("--resume", action="store_true", help="跳过 out/listings.jsonl 里已成功的 asin")
    p.add_argument("--max-tokens", type=int, default=1200)
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--out", default="out")
    return p


def read_products(path) -> list[dict]:
    """读 products.csv → list[dict]。features / keywords 保持原始分号字符串。"""
    raise NotImplementedError("TODO: read_products")


def load_done(path) -> set[str]:
    """读已有 listings.jsonl，返回已成功的 asin 集合（用于 --resume）。"""
    raise NotImplementedError("TODO: load_done")


def generate_one(product: dict, template: str, *, mock: bool,
                 max_tokens: int, temperature: float) -> dict:
    """生成一条，含"校验 → 带错误信息重试"循环。

    返回：
        {"asin", "ok", "data"|None, "failed": [...], "attempts", "cost_cny", "elapsed_s"}

    重试规则（tests 依赖 attempts 语义）：
      - 最多 3 次
      - 第 1 次 temperature 用传入值；之后降到 0（越随机越难修）
      - 校验失败时，把模型原始输出和错误信息追加进 messages 再问一次
      - 3 次都失败 → ok=False，failed 里带上最后一次的规则名
    """
    raise NotImplementedError("TODO: generate_one")


def write_report(summary: dict, out_dir: Path) -> str:
    """生成 Markdown 报告，必须包含：总条数、通过率、平均得分、
    失败规则分布（按次数降序）、总成本、平均耗时、重试率。
    """
    raise NotImplementedError("TODO: write_report")


def run(args) -> int:
    """主流程。缺模板/缺 Key 返回 2；有失败样本返回 1；全成功 0。"""
    raise NotImplementedError("TODO: run")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
