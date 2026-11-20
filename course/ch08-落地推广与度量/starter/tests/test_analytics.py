"""验收标准：7 个测试。全部离线。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics import compare as cmp     # noqa: E402
from analytics import events as ev       # noqa: E402
from analytics import metrics as mt      # noqa: E402


def e(eid, ts, user="li", ok=True, dur=6.0, cost=0.001, tool="daily-report", err=""):
    return {"event_id": eid, "ts": ts, "user": user, "tool": tool, "action": "run",
            "ok": ok, "duration_s": dur, "cost_cny": cost, "error": err}


BEFORE = [
    e("b1", "2026-11-02T09:10:00", "li", True, 5400, 0.0, "manual-report"),
    e("b2", "2026-11-03T09:10:00", "li", False, 6000, 0.0, "manual-report", "漏站"),
    e("b3", "2026-11-04T09:10:00", "wang", True, 5100, 0.0, "manual-report"),
]
AFTER = [
    e("a1", "2026-11-09T09:10:00", "li", True, 6.0, 0.0008),
    e("a2", "2026-11-10T09:10:00", "li", True, 5.0, 0.0009),
    e("a3", "2026-11-11T09:10:00", "wang", False, 4.0, 0.0007, err="对账残差超容差"),
    e("a4", "2026-11-16T09:10:00", "zhou", True, 7.0, 0.0010),
]


class TestEvents(unittest.TestCase):
    def test_去重(self):
        rows = BEFORE + [dict(BEFORE[0])]        # 同一 event_id 重复
        self.assertEqual(len(ev.dedupe(rows)), 3)

    def test_追加时幂等(self):
        import tempfile
        path = Path(tempfile.mkdtemp(prefix="ch08-")) / "ev.jsonl"
        self.assertEqual(ev.append_jsonl(path, BEFORE), 3)
        self.assertEqual(ev.append_jsonl(path, BEFORE), 0, "重复上报不应再写入")
        self.assertEqual(len(ev.load_jsonl(path)), 3)


class TestMetrics(unittest.TestCase):
    def test_核心统计(self):
        k = mt.summarize(AFTER)
        self.assertEqual(k["runs"], 4)
        self.assertEqual(k["users"], 3)
        self.assertEqual(k["days"], 4)
        self.assertAlmostEqual(k["success_rate"], 0.75)
        self.assertAlmostEqual(k["avg_duration_s"], 5.5)

    def test_周活与留存(self):
        weekly = mt.weekly_active(AFTER)
        # 11-09~11-11 一周（li、wang），11-16 下一周（zhou）
        self.assertEqual(len(weekly), 2)
        self.assertEqual(sorted(weekly.values()), [1, 2])
        weeks = sorted(weekly)
        # 前一周的人在下一周一个都没留下 —— 留存为 0，这正是"工具没人回来用"的样子
        self.assertEqual(mt.retention(AFTER, weeks[0], weeks[1]), 0.0)

    def test_节省工时(self):
        # 4 次 × 90 分钟人工 vs 工具合计 22 秒
        saved = mt.saved_hours(AFTER, manual_minutes=90)
        self.assertGreater(saved, 5.9)
        self.assertLess(saved, 6.0)

    def test_空数据不崩(self):
        k = mt.summarize([])
        self.assertEqual(k["runs"], 0)
        self.assertEqual(mt.saved_hours([], 90), 0.0)
        self.assertEqual(mt.failure_reasons([]), [])


class TestCompare(unittest.TestCase):
    def test_对比报告(self):
        r = cmp.compare(BEFORE, AFTER, manual_minutes=90, hourly_rate=90)
        self.assertEqual(r["before"]["runs"], 3)
        self.assertEqual(r["after"]["runs"], 4)
        self.assertGreater(r["saved_hours_after"], r["saved_hours_before"])
        md = cmp.render_markdown(r)
        self.assertIn("上线后", md)
        self.assertIn("节省工时", md)
        self.assertIn("人工基线", md)


if __name__ == "__main__":
    unittest.main()
