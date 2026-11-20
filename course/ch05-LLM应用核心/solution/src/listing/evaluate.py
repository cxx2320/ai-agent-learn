"""评估（参考实现）。"""

from __future__ import annotations

from . import schema


def score_listing(data: dict, product: dict) -> tuple[float, list[str]]:
    failed = schema.validate_listing(data, product)
    total = len(schema.ALL_RULES)
    return round((total - len(failed)) / total, 4), failed


def summarize(results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        return {"total": 0, "passed": 0, "pass_rate": 0.0, "avg_score": 0.0,
                "failed_rules": {}, "total_cost_cny": 0.0, "avg_elapsed_s": 0.0,
                "retry_rate": 0.0}

    passed = sum(1 for r in results if r.get("ok"))
    counts: dict[str, int] = {}
    for r in results:
        for rule in r.get("failed", []):
            counts[rule] = counts.get(rule, 0) + 1

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4),
        "avg_score": round(sum(r.get("score", 0.0) for r in results) / total, 4),
        "failed_rules": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "total_cost_cny": round(sum(r.get("cost_cny", 0.0) for r in results), 6),
        "avg_elapsed_s": round(sum(r.get("elapsed_s", 0.0) for r in results) / total, 3),
        "retry_rate": round(sum(1 for r in results if r.get("attempts", 1) > 1) / total, 4),
    }
