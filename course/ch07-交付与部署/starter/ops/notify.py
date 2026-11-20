"""告警：定时任务失败时，要让**该知道的人**在**当下**知道。

三条设计规则（违反任何一条，告警就会变成噪音）：
  1. 只有需要人处理的事才告警；"成功"不告警，写日志即可
  2. 告警内容必须能让人**不动代码就能判断**：什么时候、哪个任务、什么错、影响什么
  3. 必须有 --dry-run：静默期、调试期、CI 里都不该真发消息

本模块默认 dry-run，不联网。真实发送需要显式 --send 且配置 webhook。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime

SEVERITY_PREFIX = {"info": "ℹ️", "warn": "⚠️", "error": "🚨"}


def build_payload(title: str, lines: list[str], severity: str = "error",
                  task: str = "daily-report", at: str | None = None) -> dict:
    """构造飞书文本消息 payload（结构通用，换成钉钉/Slack 只改这里）。

    契约（tests 依赖）：
      - msg_type == "text"
      - 文本首行 = 前缀 + title
      - 文本里包含 task 名、时间、以及每一条 lines
    """
    at = at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = SEVERITY_PREFIX.get(severity, "")
    body = [f"{prefix} {title}", f"任务：{task}", f"时间：{at}"]
    body.extend(lines)
    return {"msg_type": "text", "content": {"text": "\n".join(body)}}


def send(payload: dict, *, webhook: str | None = None, dry_run: bool = True,
         timeout: int = 10) -> dict:
    """发送。dry_run=True 时只返回 payload，不联网。

    返回 {"sent": bool, "dry_run": bool, "payload": {...}, "error": str|None}
    """
    if dry_run:
        return {"sent": False, "dry_run": True, "payload": payload, "error": None}
    url = webhook or os.environ.get("FEISHU_WEBHOOK", "")
    if not url:
        return {"sent": False, "dry_run": False, "payload": payload,
                "error": "未配置 FEISHU_WEBHOOK"}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        return {"sent": True, "dry_run": False, "payload": payload, "error": None}
    except Exception as exc:                            # 告警失败不能把主流程带崩
        return {"sent": False, "dry_run": False, "payload": payload, "error": str(exc)}


def alert_from_healthcheck(health: dict, task: str = "daily-report") -> dict:
    """把健康检查结果转成一条告警（只报非 OK 项）。"""
    bad = [r for r in health.get("results", []) if r.get("level") != "OK"]
    lines = [f"• [{r['level']}] {r['name']}：{r['detail']}" for r in bad]
    if not lines:
        lines = ["全部检查通过"]
    severity = "error" if health.get("exit_code") == 2 else "warn"
    return build_payload(f"日报任务异常（退出码 {health.get('exit_code')}）",
                         lines, severity=severity, task=task)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="notify", description="告警发送（默认 dry-run）")
    p.add_argument("--title", required=True)
    p.add_argument("--line", action="append", default=[], help="正文行，可多次指定")
    p.add_argument("--severity", default="error", choices=list(SEVERITY_PREFIX))
    p.add_argument("--task", default="daily-report")
    p.add_argument("--send", action="store_true", help="真的发（默认只打印）")
    a = p.parse_args(argv)

    payload = build_payload(a.title, a.line, severity=a.severity, task=a.task)
    result = send(payload, dry_run=not a.send)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["dry_run"] or result["sent"] else 1


if __name__ == "__main__":
    sys.exit(main())
