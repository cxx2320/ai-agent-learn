"""生成示例事件流（确定性，可复现）。

模拟一家跨境公司的日报工作流：
  - 2026-11-01 ~ 11-07：手工做报表（tool=manual-report，每次约 90 分钟，成功率 60%）
  - 2026-11-08 ~ 11-28：用日报工具（tool=daily-report，每次约 6 秒，成功率 95%）
  - 4 个用户，其中 1 个中途流失（真实情况：总有人不用）

用法：python scripts/gen_events.py
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(20261119)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "events.jsonl"

USERS = ["li", "wang", "zhou", "chen"]
CHURNED = {"chen"}          # 第三周开始不再使用

WEEKS = [
    (date(2026, 11, 1), date(2026, 11, 7), "manual-report"),
    (date(2026, 11, 8), date(2026, 11, 14), "daily-report"),
    (date(2026, 11, 15), date(2026, 11, 21), "daily-report"),
    (date(2026, 11, 22), date(2026, 11, 28), "daily-report"),
]

ERRORS = ["数据源缺失", "对账残差超容差", "登录态失效", "报表字段变更"]

rows = []
seq = 0
for start, end, tool in WEEKS:
    is_manual = tool == "manual-report"
    d = start
    while d <= end:
        if d.weekday() < 5:                       # 只在工作日跑
            for user in USERS:
                if tool == "daily-report" and start >= date(2026, 11, 15) and user in CHURNED:
                    continue
                if random.random() < 0.15:        # 当天没跑
                    continue
                seq += 1
                ok = random.random() > (0.40 if is_manual else 0.05)
                dur = (random.uniform(4800, 6600) if is_manual
                       else random.uniform(3.0, 9.0))
                rows.append({
                    "event_id": f"E{seq:05d}",
                    "ts": f"{d.isoformat()}T09:{random.randint(10, 50):02d}:00",
                    "user": user,
                    "tool": tool,
                    "action": "run",
                    "ok": ok,
                    "duration_s": round(dur, 2),
                    "cost_cny": 0.0 if is_manual else round(random.uniform(0.0005, 0.002), 6),
                    "error": "" if ok else random.choice(ERRORS),
                })
        d += timedelta(days=1)

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"写入 {len(rows)} 条事件 → {OUT}")
