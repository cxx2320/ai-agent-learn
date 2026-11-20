"""Schema 校验：把"写得好不好"和"合不合规"分开。

合规是**可程序判定**的，必须 100% 通过；
写得好不好是主观的，交给评估集和人工。

规则名（字符串）是测试断言的依据，不要改。
"""

from __future__ import annotations

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
    """是否含中文字符（\u4e00-\u9fff）。"""
    raise NotImplementedError("TODO: has_chinese")


def validate_listing(data: dict, product: dict) -> list[str]:
    """返回**未通过**的规则名列表；全部通过返回 []。

    契约（tests 依赖）：
      - data 缺 title / bullets / search_terms 任一键 → 直接返回 ["结构不合法"]
      - title 的"目标关键词"来自 product["keywords"]（分号分隔），
        "含 ≥2 个"按 title.lower() 里命中的个数算
      - 禁用词在 title+bullets 拼起来的文本里查（不区分大小写）
      - bullets 不是 list 或长度不是 5 → RULE_BULLETS_5 失败，且不再查 RULE_BULLET_LEN
    """
    raise NotImplementedError("TODO: validate_listing")


def parse_json(raw: str) -> dict:
    """从模型输出里解析 JSON。

    模型经常不听话，会加 ```json 代码块或前后废话，所以要容错：
      1. 先直接 json.loads
      2. 失败则剥掉 markdown 代码块再试
      3. 再失败则截取第一个 { 到最后一个 } 再试
      4. 都不行 → 抛 ValueError("不是合法 JSON")
    """
    raise NotImplementedError("TODO: parse_json")
