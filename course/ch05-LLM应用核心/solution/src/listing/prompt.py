"""Prompt 组装（参考实现）。"""

from __future__ import annotations

from pathlib import Path

SYSTEM_PROMPT = (
    "You are a senior Amazon listing copywriter for the US marketplace. "
    "You never use promotional superlatives, guarantees, or pricing claims. "
    "You output only valid JSON."
)


def load_template(path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    return p.read_text(encoding="utf-8")


def build_messages(product: dict, template: str) -> list[dict]:
    values = {
        "title_cn": product.get("title_cn", ""),
        "category": product.get("category", ""),
        "price_usd": product.get("price_usd", ""),
        "features": (product.get("features") or "").replace(";", ", "),
        "keywords": (product.get("keywords") or "").replace(";", ", "),
    }
    user = template.format(**values)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
