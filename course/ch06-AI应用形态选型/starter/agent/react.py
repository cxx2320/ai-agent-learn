"""ReAct 循环：思考 → 选工具 → 看结果 → 再思考。

**没有刹车的 Agent 不能上线**，所以这个实现里有两个刹车：
  ① 最大步数（max_steps）：防止无限循环
  ② 重复调用检测（max_repeat）：同一个工具 + 同样的参数，连调超过 N 次就终止
     —— 只有步数上限是不够的，8 步同一个动作照样烧钱

planner 的契约（这样才测得动，不用真模型）：
    planner(question, trace) -> {"tool": "search_kb", "args": {...}}
                            或 {"final": "最终回答"}
trace 是已执行步骤的列表，planner 可以据此决定下一步。
"""

from __future__ import annotations

import json
from collections import Counter

from .tools import ToolRegistry


def _key(tool: str, args: dict) -> str:
    return tool + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False)


def run(question: str, planner, registry: ToolRegistry,
        max_steps: int = 8, max_repeat: int = 2) -> dict:
    """执行一次 ReAct。

    返回：
        {"answer": str, "steps": int, "stopped": None|"repeat"|"max_steps",
         "trace": [{"step", "tool", "args", "ok", "result"/"error"}, ...]}
    """
    trace: list[dict] = []
    counter: Counter = Counter()

    for step in range(1, max_steps + 1):
        action = planner(question, trace)

        if "final" in action:
            return {"answer": action["final"], "steps": len(trace),
                    "stopped": None, "trace": trace}

        tool = action.get("tool", "")
        args = action.get("args") or {}

        k = _key(tool, args)
        counter[k] += 1
        if counter[k] > max_repeat:
            return {"answer": f"检测到重复调用（{tool} 连续 {counter[k]} 次），已终止以防死循环",
                    "steps": len(trace), "stopped": "repeat", "trace": trace}

        res = registry.call(tool, args)
        trace.append({"step": step, "tool": tool, "args": args,
                      "ok": res["ok"],
                      **({"result": res["result"]} if res["ok"] else {"error": res["error"]})})

    return {"answer": f"无法在 {max_steps} 步内完成", "steps": len(trace),
            "stopped": "max_steps", "trace": trace}


def render_trace(result: dict) -> str:
    """把 trace 渲染成可读的执行记录（排查问题全靠它）。"""
    lines = [f"Q: {result.get('question', '')}".rstrip(),
             f"结果: {result['answer']}",
             f"步数: {result['steps']}  停止原因: {result['stopped']}"]
    for t in result["trace"]:
        body = t.get("result", t.get("error"))
        lines.append(f"  [{t['step']}] {t['tool']}({json.dumps(t['args'], ensure_ascii=False)}) "
                     f"→ {'ok' if t['ok'] else 'ERR'} {str(body)[:80]}")
    return "\n".join(lines)
