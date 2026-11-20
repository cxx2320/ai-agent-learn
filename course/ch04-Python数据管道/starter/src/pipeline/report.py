"""渲染层：把算好的数变成人看得懂的东西。

规矩：这里不读文件、不算指标，只做「拿到 dict → 吐字符串」。
产出两个东西：给业务看的 Markdown 日报，和给工程师看的异常清单。
"""

from __future__ import annotations


def render_markdown(kpis: dict, bridge: dict, anomalies: list[dict], rows: list[dict]) -> str:
    """生成日报 Markdown。

    必须包含（测试会查字符串）：
      - 标题行："# 多站点日报"
      - "## 核心指标" 段，含销售额/订单数/退款率/ACOS/TACOS
      - "## 对账" 段，含 "残差" 和残差值（保留 2 位小数）
      - "## 异常清单" 段，列出 anomalies 的 type 和 detail
      - 如果 bridge["residual"] 的绝对值 > 0 且超过容差，在文首加一行 ⚠️ 提示

    排版要求：金额带千分位和 2 位小数；百分比保留 2 位；没有数据写 "—" 而不是 "None"。
    """
    raise NotImplementedError("TODO: render_markdown")


def render_anomalies_csv(anomalies: list[dict]) -> str:
    """异常清单 → CSV 文本（utf-8-sig 由调用方处理 BOM）。
    列顺序固定：severity,type,ref,detail
    """
    raise NotImplementedError("TODO: render_anomalies_csv")
