"""模型层：把"调模型"抽象成一个函数，这样才测得动、换得掉。

两种实现共用一个签名 complete(...)：
  - mock=True  → 本地确定性假模型（不联网、零成本、CI 可跑）
  - mock=False → 调用 OpenAI 兼容接口（DeepSeek / 通义 / OpenAI 都行）

真实实现只用标准库 urllib，避免装包。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# 单价：元 / 百万 token（按需改）
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
    """粗估 token 数：英文约 4 字符/token，中文约 1.5 字符/token。

    真实项目应使用模型自带的 usage 字段；这里保留估算是为了 mock 模式也能算成本。
    """
    raise NotImplementedError("TODO: estimate_tokens")


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """按 PRICES 算成本（元）。未知模型按 deepseek-chat 的单价。"""
    raise NotImplementedError("TODO: estimate_cost")


def mock_complete(prompt_text: str) -> str:
    """确定性假模型：从 prompt 里抠出关键词和卖点，拼一份**结构合法**的 JSON。

    只保证合规，不保证质量 —— 这正是 mock 的用途：验证管道，不是验证文案。

    契约（tests 依赖）：
      - 返回 str，且能被 json.loads 解析
      - 含 title / bullets(5 条) / search_terms 三个键
      - 必须能通过 schema.validate_listing 的全部规则（对 data/products.csv 的 8 个产品）
      - 同样的输入必须产出同样的输出（幂等，方便做快照测试）
    """
    raise NotImplementedError("TODO: mock_complete")


def complete(messages: list[dict], *, model: str | None = None,
             temperature: float = 0.3, max_tokens: int = 1200,
             mock: bool = False, timeout: int = 60) -> LLMResult:
    """统一入口。

    mock=True：把 messages 拼成文本交给 mock_complete，usage 用估算值，cost 照算。
    mock=False：
      - key 从环境变量 LLM_API_KEY 读，缺失则抛 RuntimeError("缺少 LLM_API_KEY")
      - POST {base_url}/chat/completions，body: model/messages/temperature/max_tokens
      - 429 指数退避重试（最多 3 次，1s/2s/4s）；5xx 重试 1 次；4xx 不重试
      - 优先使用响应里的 usage（prompt_tokens/completion_tokens）
    """
    raise NotImplementedError("TODO: complete")
