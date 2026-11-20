"""CLI（参考实现）。"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path

from . import evaluate, llm, prompt, schema

log = logging.getLogger("listing")

ROOT = Path(__file__).resolve().parents[2]      # 项目根（含 data/ prompts/）


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="listing", description="Listing 批量生成器")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="用本地假模型（不联网）")
    mode.add_argument("--real", action="store_true", help="调用真实模型")
    p.add_argument("--limit", type=int, default=0, help="只跑前 N 条，0 表示全部")
    p.add_argument("--resume", action="store_true", help="跳过已成功的 asin")
    p.add_argument("--max-tokens", type=int, default=1200)
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--prompt", default="listing_v1.txt", help="prompts/ 下的模板文件名")
    p.add_argument("--out", default="out")
    return p


def read_products(path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_done(path) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    done = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("ok") and rec.get("asin"):
            done.add(rec["asin"])
    return done


def generate_one(product: dict, template: str, *, mock: bool, max_tokens: int,
                 temperature: float, completer=None) -> dict:
    completer = completer or llm.complete
    messages = prompt.build_messages(product, template)
    cost = 0.0
    elapsed = 0.0
    last_failed: list[str] = []

    for attempt in range(1, 4):
        temp = temperature if attempt == 1 else 0.0
        res = completer(messages, temperature=temp, max_tokens=max_tokens, mock=mock)
        cost += res.usage.cost_cny
        elapsed += res.elapsed_s

        try:
            data = schema.parse_json(res.text)
        except ValueError as exc:
            last_failed = ["JSON 解析失败"]
            messages = messages + [
                {"role": "assistant", "content": res.text},
                {"role": "user", "content": f"输出不合法：{exc}。请只返回合法 JSON。"},
            ]
            continue

        failed = schema.validate_listing(data, product)
        if not failed:
            return {"asin": product["asin"], "ok": True, "data": data, "failed": [],
                    "attempts": attempt, "cost_cny": round(cost, 6),
                    "elapsed_s": round(elapsed, 3)}

        last_failed = failed
        messages = messages + [
            {"role": "assistant", "content": res.text},
            {"role": "user", "content": f"输出不满足要求：{'；'.join(failed)}。"
                                        f"请修正后只返回合法 JSON。"},
        ]

    return {"asin": product["asin"], "ok": False, "data": None, "failed": last_failed,
            "attempts": 3, "cost_cny": round(cost, 6), "elapsed_s": round(elapsed, 3)}


def write_report(summary: dict, out_dir: Path, mode: str) -> str:
    lines = ["# Listing 生成评估报告", ""]
    if mode == "mock":
        lines += ["> ⚠️ 本报告来自 `--mock` 假模型，**只能证明管道通，不能证明文案质量**。", ""]
    lines += [
        f"- 模式：{mode}",
        f"- 总条数：{summary['total']}",
        f"- 通过率：{summary['pass_rate']:.2%}（{summary['passed']}/{summary['total']}）",
        f"- 平均得分：{summary['avg_score']:.2%}",
        f"- 重试率：{summary['retry_rate']:.2%}",
        f"- 总成本：{summary['total_cost_cny']:.6f} 元",
        f"- 平均耗时：{summary['avg_elapsed_s']:.2f} 秒",
        "",
        "## 失败规则分布",
        "",
    ]
    if summary["failed_rules"]:
        lines += ["| 规则 | 次数 |", "|---|---|"]
        for rule, n in summary["failed_rules"].items():
            lines.append(f"| {rule} | {n} |")
    else:
        lines.append("无失败。")
    return "\n".join(lines) + "\n"


def run(args) -> int:
    template_path = ROOT / "prompts" / args.prompt
    try:
        template = prompt.load_template(template_path)
    except FileNotFoundError:
        log.error("模板不存在：%s", template_path)
        return 2

    mock = not args.real
    if not mock and not os.environ.get("LLM_API_KEY"):
        log.error("--real 需要环境变量 LLM_API_KEY")
        return 2

    products = read_products(ROOT / "data" / "products.csv")
    if args.limit:
        products = products[:args.limit]

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    listings_path = out_dir / "listings.jsonl"
    failed_path = out_dir / "failed.jsonl"

    done = load_done(listings_path) if args.resume else set()
    results, listings, failed_records = [], [], []

    for p in products:
        if p["asin"] in done:
            log.info("跳过（已完成）：%s", p["asin"])
            continue
        r = generate_one(p, template, mock=mock, max_tokens=args.max_tokens,
                         temperature=args.temperature)
        score, _ = (evaluate.score_listing(r["data"], p) if r["ok"] else (0.0, []))
        r["score"] = score
        results.append(r)
        if r["ok"]:
            listings.append({"asin": p["asin"], **r["data"],
                             "usage": {"cost_cny": r["cost_cny"]},
                             "attempts": r["attempts"]})
        else:
            failed_records.append({"asin": p["asin"], "failed": r["failed"],
                                   "attempts": r["attempts"]})
        log.info("%s attempts=%d ok=%s score=%.2f", p["asin"], r["attempts"], r["ok"], score)

    if listings:
        with open(listings_path, "a", encoding="utf-8") as f:
            for rec in listings:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if failed_records:
        with open(failed_path, "a", encoding="utf-8") as f:
            for rec in failed_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    summary = evaluate.summarize(results)
    report = write_report(summary, out_dir, "real" if args.real else "mock")
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    print(report)
    return 0 if summary["total"] and summary["passed"] == summary["total"] else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
