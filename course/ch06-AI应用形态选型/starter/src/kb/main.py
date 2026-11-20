"""CLI：python run.py "问题"

    python run.py "月度仓储费怎么算"
    python run.py "FBA 配送费和佣金有什么区别" --k 5
    python run.py "今天天气怎么样"        # 应该拒答
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import answer as ans
from . import chunk as ck
from . import retrieve as rt

ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kb", description="平台规则问答（离线 RAG）")
    p.add_argument("question", help="你的问题")
    p.add_argument("--k", type=int, default=3, help="取前 k 个片段")
    p.add_argument("--min-score", type=float, default=0.05, help="低于该分数视为无结果")
    p.add_argument("--corpus", default=str(ROOT / "corpus"))
    return p


def run(args) -> int:
    chunks = ck.load_docs(args.corpus)
    index = rt.build_index(chunks)
    hits = rt.search(index, args.question, k=args.k, min_score=args.min_score)
    result = ans.answer(args.question, hits)

    print(f"Q: {result.question}\n")
    print(result.text)
    if result.citations:
        print("\n引用：")
        for c in result.citations:
            print(f"  - {c['doc']} · {c['section']}  (score {c['score']})")
    else:
        print("\n（无引用：本次未在知识库中命中任何片段）")
    return 0 if result.hits else 3


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
