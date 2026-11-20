"""评估：把"感觉不错"变成"通过率 87.5%，失败集中在标题长度"。

只用规则判定，不调模型 —— 便宜、稳定、可解释。
主观质量（好不好卖）留给人工抽样，不要在这里假装能算。
"""

from __future__ import annotations


def score_listing(data: dict, product: dict) -> tuple[float, list[str]]:
    """返回 (得分 0~1, 未通过的规则名列表)。

    得分 = 通过规则数 / 总规则数（总规则数用 schema.ALL_RULES 的长度）。
    """
    raise NotImplementedError("TODO: score_listing")


def summarize(results: list[dict]) -> dict:
    """汇总一份评估报告。

    results 每项形如：
        {"asin": "...", "ok": True/False, "score": 0.86, "failed": [...],
         "cost_cny": 0.0013, "elapsed_s": 3.2, "attempts": 1}

    返回：
        {"total": n, "passed": n, "pass_rate": 0.875,
         "avg_score": 0.93,
         "failed_rules": {"标题 60-180 字符": 2, ...},   # 按出现次数降序
         "total_cost_cny": 0.0104, "avg_elapsed_s": 3.2,
         "retry_rate": 0.25}
    空输入要返回全 0，不能除零崩掉。
    """
    raise NotImplementedError("TODO: summarize")
