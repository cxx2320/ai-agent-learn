"""Schema 校验（参考实现）。"""

from __future__ import annotations

import json
import re

FORBIDDEN = ("best", "#1", "no.1", "guarantee", "free shipping", "cheap", "sale", "discount")

RULE_TITLE_LEN = "标题 60-180 字符"
RULE_TITLE_EN = "标题全英文"
RULE_BULLETS_5 = "五点恰好 5 条"
RULE_BULLET_LEN = "每条 120-300 字符"
RULE_KEYWORDS = "含 ≥2 个目标关键词"
RULE_FORBIDDEN = "无禁用词"
RULE_SEARCH_TERMS = "search_terms 1-10 条"

ALL_RULES = (
    RULE_TITLE_LEN, RULE_TITLE_EN, RULE_BULLETS_5,
    RULE_BULLET_LEN, RULE_KEYWORDS, RULE_FORBIDDEN, RULE_SEARCH_TERMS,
)


def has_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _keywords_of(product: dict) -> list[str]:
    return [k.strip().lower() for k in (product.get("keywords") or "").split(";") if k.strip()]


def validate_listing(data: dict, product: dict) -> list[str]:
    if not isinstance(data, dict) or not {"title", "bullets", "search_terms"} <= set(data):
        return ["结构不合法"]

    failed: list[str] = []
    title = data.get("title") or ""
    bullets = data.get("bullets")
    terms = data.get("search_terms") or []

    if not (60 <= len(title) <= 180):
        failed.append(RULE_TITLE_LEN)
    if has_chinese(title):
        failed.append(RULE_TITLE_EN)

    if not isinstance(bullets, list) or len(bullets) != 5:
        failed.append(RULE_BULLETS_5)
    elif not all(isinstance(b, str) and 120 <= len(b) <= 300 for b in bullets):
        failed.append(RULE_BULLET_LEN)

    kws = _keywords_of(product)
    if sum(1 for k in kws if k in title.lower()) < 2:
        failed.append(RULE_KEYWORDS)

    blob = (title + " " + " ".join(b for b in bullets if isinstance(b, str))).lower()
    if any(w in blob for w in FORBIDDEN):
        failed.append(RULE_FORBIDDEN)

    if not isinstance(terms, list) or not (1 <= len(terms) <= 10) \
            or any(not isinstance(t, str) or len(t) > 50 for t in terms):
        failed.append(RULE_SEARCH_TERMS)

    return failed


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json(raw: str) -> dict:
    raw = (raw or "").strip()
    candidates = [raw]

    m = _FENCE.search(raw)
    if m:
        candidates.append(m.group(1).strip())

    lo, hi = raw.find("{"), raw.rfind("}")
    if lo != -1 and hi > lo:
        candidates.append(raw[lo:hi + 1])

    for text in candidates:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    raise ValueError("不是合法 JSON")
