"""使用事件：工具到底有没有人用，只能靠埋点回答。

设计要点：
  1. 事件带 **event_id**，重复上报要能去重（幂等）——否则统计会虚高
  2. 只记"发生了什么"，不在写入时做聚合（聚合留在分析侧）
  3. 不记敏感信息：不存订单明文、不存邮箱，用户用代号
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

FIELDS = ("event_id", "ts", "user", "tool", "action", "ok",
          "duration_s", "cost_cny", "error")


def make_event(user: str, tool: str, action: str = "run", ok: bool = True,
               duration_s: float = 0.0, cost_cny: float = 0.0,
               error: str = "", ts: str | None = None,
               event_id: str | None = None) -> dict:
    return {
        "event_id": event_id or uuid.uuid4().hex[:12],
        "ts": ts or datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "user": user,
        "tool": tool,
        "action": action,
        "ok": bool(ok),
        "duration_s": round(float(duration_s), 3),
        "cost_cny": round(float(cost_cny), 6),
        "error": error,
    }


def load_jsonl(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event_id"):
            out.append(rec)
    return out


def append_jsonl(path, events: list[dict]) -> int:
    """追加写入，按 event_id 去重。返回实际写入条数。

    为什么必须去重：重试、补跑、断点续传都会导致同一事件被上报两次。
    不去重的话，你的"使用次数"会凭空翻倍，然后你拿着虚高的数据去汇报。
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    seen = {e["event_id"] for e in load_jsonl(p)}
    fresh = [e for e in events if e.get("event_id") and e["event_id"] not in seen]
    if fresh:
        with open(p, "a", encoding="utf-8") as f:
            for e in fresh:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(fresh)


def dedupe(events: list[dict]) -> list[dict]:
    seen, out = set(), []
    for e in events:
        eid = e.get("event_id")
        if eid in seen:
            continue
        seen.add(eid)
        out.append(e)
    return out
