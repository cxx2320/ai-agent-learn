"""脚本化 planner：不调模型，按预设步骤执行。

为什么要有它：
  1. 测试 ReAct 循环不需要花 API 的钱
  2. 它把"模型决策"和"循环/刹车"解耦了——这是可测试性的前提
  3. 真实项目里，很多所谓"Agent"其实可以退化成固定流程，先跑通再谈智能

真接模型时，只要实现一个
    planner(question, trace) -> {"tool":..., "args":...} | {"final":...}
把模型返回的 JSON 塞进这个结构即可，循环与刹车完全不用改。
"""

from __future__ import annotations


class ScriptedPlanner:
    """按顺序执行预设动作，走完后返回 final。"""

    def __init__(self, actions: list[dict], final: str):
        self.actions = list(actions)
        self.final = final
        self.i = 0

    def __call__(self, question: str, trace: list[dict]) -> dict:
        if self.i < len(self.actions):
            act = self.actions[self.i]
            self.i += 1
            return act
        return {"final": self.final}


def loop_planner(tool: str, args: dict) -> ScriptedPlanner:
    """永远调同一个工具——用来触发"重复调用"刹车。"""
    return ScriptedPlanner([{"tool": tool, "args": dict(args)}] * 10, "不该走到这里")


def build_demo_registry():
    """演示用的两个工具：查知识库 + 简单计算。"""
    import sys
    from pathlib import Path

    # kb 在 starter/src 下，直接 `python -m agent.planner` 时不在 sys.path 里
    src = Path(__file__).resolve().parents[1] / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from kb import chunk as kb_chunk
    from kb import retrieve as kb_retrieve
    from .tools import ToolRegistry

    corpus = Path(__file__).resolve().parents[1] / "corpus"
    chunks = kb_chunk.load_docs(corpus)
    index = kb_retrieve.build_index(chunks)

    reg = ToolRegistry()

    def search_kb(q: str) -> list[dict]:
        hits = kb_retrieve.search(index, q, k=3)
        if not hits:
            raise LookupError(f"知识库无结果：{q}")
        return [{"doc": c.doc, "section": c.section, "score": s, "text": c.text[:100]}
                for c, s in hits]

    def calc(expr: str) -> float:
        # 教学用：只允许数字与 + - * / ( ) 和小数点，避免任意代码执行
        allowed = set("0123456789+-*/(). ")
        if not set(expr) <= allowed:
            raise ValueError("表达式含非法字符")
        return round(eval(expr, {"__builtins__": {}}, {}), 2)

    reg.register("search_kb", "在平台规则知识库里检索，返回带出处的片段",
                 ("q",), search_kb)
    reg.register("calc", "计算一个算术表达式，如 3*29.99", ("expr",), calc)
    return reg


def demo() -> int:
    from .react import render_trace, run

    reg = build_demo_registry()
    planner = ScriptedPlanner(
        [{"tool": "search_kb", "args": {"q": "退货 利润"}},
         {"tool": "calc", "args": {"expr": "3 * 29.99"}}],
        "退货会同时损失本金、配送费与不可售损耗，所以退款 3 单 29.99 美元的直接损失约 89.97 美元。",
    )
    result = run("退货率高会影响利润吗？顺便算一下 3 单 29.99 美元是多少", planner, reg)
    print(render_trace({**result, "question": "退货率高会影响利润吗？顺便算 3*29.99"}))
    return 0 if result["stopped"] is None else 1


if __name__ == "__main__":
    import sys
    sys.exit(demo())
