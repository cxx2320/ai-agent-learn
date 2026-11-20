"""检索：TF-IDF + 余弦相似度（纯标准库，不需要向量库）。

为什么先做 TF-IDF 而不是 embedding：
  1. 零依赖、可离线、结果可解释（能说清为什么命中）
  2. 中小知识库（几百个 chunk）TF-IDF 往往够用
  3. 你要先建立"检索质量决定一切"的判断力，再谈换向量模型

中文必须处理：中文没有空格，按英文分词会整段变成一个 token。
本实现用「中文双字切分 + 英文按词」的混合分词。
"""

from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """英文小写按词，中文按双字（bigram）。

    "月度仓储费" → ["月度", "度仓", "仓储", "储费"]
    """
    tokens: list[str] = []
    for m in _WORD.finditer(text or ""):
        s = m.group(0)
        if s[0].isascii():
            tokens.append(s.lower())
        elif len(s) == 1:
            tokens.append(s)
        else:
            tokens.extend(s[i:i + 2] for i in range(len(s) - 1))
    return tokens


def build_index(chunks) -> dict:
    """建立倒排所需的统计量：每块 tf、df、idf、向量模长。

    返回 {"chunks": [...], "tf": [...], "idf": {...}, "norm": [...]}
    """
    tfs = [Counter(tokenize(c.text)) for c in chunks]
    df: Counter = Counter()
    for tf in tfs:
        df.update(set(tf))
    n = max(1, len(chunks))
    idf = {t: math.log((n + 1) / (d + 1)) + 1 for t, d in df.items()}
    norms = []
    for tf in tfs:
        s = sum((f * idf.get(t, 0.0)) ** 2 for t, f in tf.items())
        norms.append(math.sqrt(s) or 1.0)
    return {"chunks": list(chunks), "tf": tfs, "idf": idf, "norm": norms}


def score_one(index: dict, qi: int, qvec: dict, qnorm: float) -> float:
    tf = index["tf"][qi]
    idf = index["idf"]
    dot = sum(qvec[t] * f * idf.get(t, 0.0) for t, f in tf.items() if t in qvec)
    return dot / (qnorm * index["norm"][qi])


def search(index: dict, query: str, k: int = 3, min_score: float = 0.05,
           boost_weight: float = 0.30) -> list[tuple]:
    """返回 [(chunk, score), ...]，按分数降序，低于 min_score 的丢掉。

    min_score 是**拒答阈值**：没有它，RAG 会对着"今天天气"也能编出一段答案。

    boost_weight 是**重排**：如果问题里的词命中了小节标题，额外加分。
    没有这一步时，问"月度仓储费"，排第一的可能是同文档里篇幅更长的
    "长期仓储费"——文档对了，章节错了，答案就会答偏。
    """
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    q_count = Counter(q_tokens)
    idf = index["idf"]
    qvec = {t: c * idf.get(t, 0.0) for t, c in q_count.items() if t in idf}
    if not qvec:
        return []
    qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0

    scored = []
    for i, chunk in enumerate(index["chunks"]):
        base = score_one(index, i, qvec, qnorm)
        sec_tokens = set(tokenize(chunk.section))
        overlap = len(sec_tokens & set(q_tokens)) / max(1, len(set(q_tokens)))
        s = base + boost_weight * overlap
        if s >= min_score:
            scored.append((chunk, round(s, 4)))
    scored.sort(key=lambda x: -x[1])
    return scored[:k]
