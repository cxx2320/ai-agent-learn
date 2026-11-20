"""模型层（参考实现）：mock 与 real 共用一个签名。"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

PRICES = {
    "deepseek-chat": (1.0, 2.0),
    "gpt-4o-mini": (1.0, 4.0),
}
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
DEFAULT_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")


@dataclass
class Usage:
    model: str
    input_tokens: int
    output_tokens: int
    cost_cny: float


@dataclass
class LLMResult:
    text: str
    usage: Usage
    elapsed_s: float


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk / 1.5 + other / 4) + 1


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICES.get(model, PRICES["deepseek-chat"])
    return round((input_tokens * pin + output_tokens * pout) / 1_000_000, 8)


# ---------------------------------------------------------------- mock
LABELS = ("SMART DESIGN", "HIGH CAPACITY", "EASY TO USE", "BUILT TO LAST", "READY TO GO")


def _grab(prompt_text: str, label: str) -> list[str]:
    for line in prompt_text.splitlines():
        line = line.strip()
        if line.startswith(label):
            body = line[len(label):]
            return [x.strip() for x in re.split(r"[,，;；]", body) if x.strip()]
    return []


def mock_complete(prompt_text: str) -> str:
    """从 prompt 里抠关键词/卖点，拼一份必定合规的 JSON。"""
    kws = _grab(prompt_text, "目标关键词：") or ["desk gadget"]
    feats = _grab(prompt_text, "卖点：") or ["durable build"]
    k1 = kws[0].lower()
    k2 = (kws[1] if len(kws) > 1 else k1).lower()

    feat_txt = ", ".join(f.title() for f in feats[:3])
    title = f"{k1.title()} {k2.title()} - {feat_txt} for Home Office and Travel"
    if len(title) > 180:
        title = title[:177].rstrip() + "..."
    while len(title) < 60:
        title += " with Premium Build"

    bullets = []
    for i, label in enumerate(LABELS):
        feat = feats[i % len(feats)].title()
        text = (f"{label}: {feat} keeps your workspace tidy and your devices powered "
                f"through the whole day.")
        while len(text) < 120:
            text += " Designed for daily use at home, in the office or on the go."
        if len(text) > 300:
            text = text[:296].rstrip() + " ..."
        bullets.append(text)

    terms = [t.lower()[:50] for t in kws[:5]]
    return json.dumps({"title": title, "bullets": bullets, "search_terms": terms},
                      ensure_ascii=False)


# ---------------------------------------------------------------- real
def _post(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def complete(messages: list[dict], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 1200,
             mock: bool = False, timeout: int = 60) -> LLMResult:
    model = model or DEFAULT_MODEL
    started = time.time()

    if mock:
        prompt_text = "\n".join(m.get("content", "") for m in messages)
        text = mock_complete(prompt_text)
        usage = Usage(model=f"mock:{model}",
                      input_tokens=estimate_tokens(prompt_text),
                      output_tokens=estimate_tokens(text),
                      cost_cny=estimate_cost(model, estimate_tokens(prompt_text),
                                             estimate_tokens(text)))
        return LLMResult(text=text, usage=usage, elapsed_s=round(time.time() - started, 3))

    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 LLM_API_KEY")

    url = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    headers = {"Authorization": f"Bearer {api_key}"}

    delay = 1.0
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            body = _post(url, payload, headers, timeout)
            text = body["choices"][0]["message"]["content"]
            u = body.get("usage") or {}
            pin = int(u.get("prompt_tokens") or estimate_tokens(str(messages)))
            pout = int(u.get("completion_tokens") or estimate_tokens(text))
            return LLMResult(text=text,
                             usage=Usage(model=model, input_tokens=pin, output_tokens=pout,
                                         cost_cny=estimate_cost(model, pin, pout)),
                             elapsed_s=round(time.time() - started, 3))
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 429:
                time.sleep(delay)
                delay *= 2
                continue
            if 500 <= e.code < 600 and attempt == 0:
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"调用失败：{last_error}")
