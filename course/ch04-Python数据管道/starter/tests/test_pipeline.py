"""验收标准：9 个测试。

跑法：
    cd starter
    python -m unittest discover -s tests -v

这些测试就是本章的验收清单。不要为了让测试通过而改测试——
如果你认为某个断言错了，来问我，我们一起判断是测试错了还是你想错了。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.config import load_config            # noqa: E402
from pipeline.transform import (                    # noqa: E402
    build_daily_asin,
    compute_kpis,
    dedupe_by,
    find_anomalies,
    load_sources,
    reconcile,
    site_date_from_bj,
)
from pipeline.report import render_markdown         # noqa: E402


def setUpModule():
    """全模块共用一个 cfg 和一次数据加载，避免每个测试都读盘。"""
    global CFG, SRC, ROWS, KPIS, BRIDGE
    CFG = load_config(ROOT / "config" / "settings.yaml")
    assert CFG.data_dir.exists(), f"数据目录不存在：{CFG.data_dir}"
    SRC = load_sources(CFG)
    ROWS = build_daily_asin(CFG, "2026-11-01", "2026-11-30")
    KPIS = compute_kpis(ROWS)
    BRIDGE = reconcile(ROWS, dedupe_by(SRC["settlement"], "transaction_id"))


class TestTimezone(unittest.TestCase):
    def test_跨日换算(self):
        # 北京时间 12-01 凌晨 = 站点 11-30
        self.assertEqual(site_date_from_bj("2026-12-01 02:00:00"), "2026-11-30")

    def test_同日换算(self):
        # 北京时间 11-15 20:00 = 站点 11-15 04:00
        self.assertEqual(site_date_from_bj("2026-11-15 20:00:00"), "2026-11-15")


class TestDedupe(unittest.TestCase):
    def test_结算去重(self):
        raw = len(SRC["settlement"])
        deduped = len(dedupe_by(SRC["settlement"], "transaction_id"))
        self.assertEqual(raw - deduped, 2, "本数据集应有 2 笔重复入账")


class TestWideTable(unittest.TestCase):
    def test_行数(self):
        # 6 ASIN × 30 天；0 单的日子也必须有行
        self.assertEqual(len(ROWS), 180)

    def test_销售额合计(self):
        self.assertAlmostEqual(sum(r["sales_usd"] for r in ROWS), 46322.64, places=2)

    def test_广告费合计(self):
        # 父体广告必须摊到子体，否则会小于这个数
        self.assertAlmostEqual(sum(r["ad_spend_usd"] for r in ROWS), 2362.54, places=2)


class TestReconcile(unittest.TestCase):
    def test_残差为0(self):
        self.assertAlmostEqual(BRIDGE["residual"], 0.00, places=2)
        self.assertAlmostEqual(BRIDGE["settlement_net"], 26541.49, places=2)


class TestKpis(unittest.TestCase):
    def test_acos(self):
        self.assertAlmostEqual(KPIS["acos"], 0.2958, places=3)


class TestReport(unittest.TestCase):
    def test_日报内容(self):
        md = render_markdown(KPIS, BRIDGE, find_anomalies(CFG, ROWS, SRC), ROWS)
        self.assertIn("对账", md)
        self.assertIn("残差", md)
        self.assertIn("核心指标", md)


if __name__ == "__main__":
    unittest.main()
