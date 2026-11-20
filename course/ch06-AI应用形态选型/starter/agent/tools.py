"""工具注册表：Agent 能做什么，由这里决定。

三条设计原则（对应讲义 6.5）：
  1. 一个工具只做一件事，参数尽量少
  2. 失败要**显式返回错误码**，不要抛异常穿透到循环里
  3. 工具清单就是白名单：不在表里的名字一律拒绝（防幻觉调用）

返回统一结构：
    {"ok": True,  "result": ...}
    {"ok": False, "error": "unknown_tool:xxx" / "missing_param:q" / "tool_error:..."}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    params: tuple[str, ...]
    func: Callable[..., Any]


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, name: str, description: str, params: tuple[str, ...],
                 func: Callable[..., Any]) -> None:
        self.tools[name] = Tool(name, description, params, func)

    def names(self) -> list[str]:
        return sorted(self.tools)

    def describe(self) -> list[dict]:
        return [{"name": t.name, "description": t.description, "params": list(t.params)}
                for t in self.tools.values()]

    def call(self, name: str, args: dict | None = None) -> dict:
        args = args or {}
        tool = self.tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"unknown_tool:{name}"}

        missing = [p for p in tool.params if p not in args]
        if missing:
            return {"ok": False, "error": f"missing_param:{','.join(missing)}"}

        extra = [k for k in args if k not in tool.params]
        if extra:
            return {"ok": False, "error": f"unexpected_param:{','.join(extra)}"}

        try:
            return {"ok": True, "result": tool.func(**args)}
        except Exception as exc:                      # 工具内部错误不外抛
            return {"ok": False, "error": f"tool_error:{type(exc).__name__}:{exc}"}
