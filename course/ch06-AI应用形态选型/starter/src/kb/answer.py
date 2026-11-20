"""生成：把检索结果组装成带引用的答案。

两个铁律：
  1. 检索不到就**拒答**，不许编（"知识库里没有"是一个合格答案）
  2. 每句话都要能**追溯到原文**（citations），否则业务没法核对

本模块同样支持 mock / real 双模式：mock 直接用原文摘要拼答案，不调模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field

NO_ANSWER = "知识库中没有找到相关规定。建议查阅平台官方文档，或补充该主题的资料后再试。"


@dataclass
class Answer:
    question: str
    text: str
    citations: list[dict] = field(default_factory=list)
    hits: int = 0


def _mock_answer(question: str, hits: list[tuple]) -> str:
    top_chunk, score = hits[0]
    body = top_chunk.text.strip().replace("\n", " ")
    if len(body) > 180:
        body = body[:180] + "…"
    return f"根据《{top_chunk.doc} · {top_chunk.section}》：{body}"


def answer(question: str, hits: list[tuple], *, mock: bool = True) -> Answer:
    """把检索结果变成答案。

    契约（tests 依赖）：
      - hits 为空 → 返回 NO_ANSWER，citations 为 []
      - 有命中 → citations 至少 1 条，每条形如
        {"doc": 文件名, "section": 章节, "score": 浮点}
      - citations 的 doc 必须来自 corpus（可追溯）
      - mock=True 时不联网；mock=False 时才允许调模型（本骨架未实现，抛 NotImplementedError 也可）
    """
    if not hits:
        return Answer(question=question, text=NO_ANSWER, citations=[], hits=0)
    citations = [{"doc": c.doc, "section": c.section, "score": s} for c, s in hits]
    return Answer(question=question, text=_mock_answer(question, hits),
                  citations=citations, hits=len(hits))
