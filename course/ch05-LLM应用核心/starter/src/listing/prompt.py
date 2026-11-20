"""Prompt 组装：模板独立成文件，变量用占位符。

为什么不 f-string 拼在代码里：改一句话要改代码、要重新跑测试、还没版本号。
"""

from __future__ import annotations

from pathlib import Path

SYSTEM_PROMPT = (
    "You are a senior Amazon listing copywriter for the US marketplace. "
    "You never use promotional superlatives, guarantees, or pricing claims. "
    "You output only valid JSON."
)


def load_template(path) -> str:
    """读模板文件。找不到就抛 FileNotFoundError（别静默用默认值，否则改了没生效你不知道）。"""
    raise NotImplementedError("TODO: load_template")


def build_messages(product: dict, template: str) -> list[dict]:
    """把产品信息填进模板，返回 messages。

    契约（tests 依赖）：
      - 返回 [{"role":"system",...}, {"role":"user",...}]
      - user 内容里不应再出现 {title_cn} 这类未替换的占位符
      - product 的 features / keywords 是分号分隔字符串，
        填进去时替换成 ", " 和 ", "（把 ; 换成逗号，读起来更像人话）
    """
    raise NotImplementedError("TODO: build_messages")
