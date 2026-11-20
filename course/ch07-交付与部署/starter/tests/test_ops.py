"""运维件验收测试：8 个。全部离线、自带夹具，不依赖其他章节。

夹具写在系统临时目录的**根层**（不再建子目录）——某些受控环境下
临时目录里不允许再建子目录，测试不应该因此变红。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops import healthcheck as hc      # noqa: E402
from ops import notify as nf           # noqa: E402

BIZ_HEADER = ("report_date,asin,sessions,page_views,units_ordered,"
              "ordered_product_sales_usd,units_refunded,refund_amount_usd,buy_box_pct\n")


def _tmp(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def make_fixture(latest="2026-11-30", residual="0.00", make_outputs=True):
    """造两个目录：一个放数据源，一个放产物。"""
    data = _tmp("ch07-data-")
    out = _tmp("ch07-out-")

    (data / "business_report_us.csv").write_text(
        BIZ_HEADER + f"{latest},B0C1AAA1,120,200,5,149.95,0,0.00,95\n", encoding="utf-8")

    if make_outputs:
        (out / "daily_asin.csv").write_text(
            "date,asin,sales_usd\n" + (latest + ",B0C1AAA1,149.95\n") * 12, encoding="utf-8")
        report = (
            f"# 多站点日报\n\n- 数据区间：{latest} ~ {latest}\n- ASIN 数：6\n- 明细行数：180\n\n"
            "## 核心指标\n\n| 指标 | 数值 |\n|---|---|\n"
            "| 销售额（未扣退款） | 46,322.64 |\n| 订单数 | 1,964 |\n| ACOS | 29.58% |\n\n"
            f"## 对账\n\n| **残差** | **{residual}** |\n"
        )
        (out / "report.md").write_text(report, encoding="utf-8")

    return data, out


class TestHealthcheck(unittest.TestCase):
    def test_全绿时退出码为0(self):
        data, out = make_fixture()
        rep = hc.run(data, out, "2026-11-30", 48, 1.0, 0.0)
        self.assertEqual(rep.exit_code, 0, [r.__dict__ for r in rep.results])

    def test_缺产物时致命(self):
        data, out = make_fixture(make_outputs=False)
        rep = hc.run(data, out, "2026-11-30", 48, 1.0, 0.0)
        self.assertEqual(rep.exit_code, 2)
        names = " ".join(r.name for r in rep.results if r.level == hc.CRIT)
        self.assertIn("daily_asin.csv", names)

    def test_数据过期时致命(self):
        data, out = make_fixture(latest="2026-11-20")
        rep = hc.run(data, out, "2026-11-30", 48, 1.0, 0.0)
        self.assertEqual(rep.exit_code, 2)
        self.assertIn("数据新鲜度", " ".join(r.name for r in rep.results if r.level == hc.CRIT))

    def test_残差超容差时致命(self):
        data, out = make_fixture(residual="12.50")
        rep = hc.run(data, out, "2026-11-30", 48, 1.0, 0.0)
        self.assertEqual(rep.exit_code, 2)
        self.assertIn("对账残差", " ".join(r.name for r in rep.results if r.level == hc.CRIT))

    def test_可输出JSON(self):
        data, out = make_fixture()
        payload = hc.run(data, out, "2026-11-30", 48, 1.0, 0.0).to_dict()
        self.assertEqual(payload["exit_code"], 0)
        json.dumps(payload)          # 必须可序列化，否则告警系统接不了


class TestNotify(unittest.TestCase):
    def test_payload结构(self):
        p = nf.build_payload("日报失败", ["• 残差 12.5 超容差"], severity="error",
                             task="daily-report", at="2026-11-19 08:30:00")
        self.assertEqual(p["msg_type"], "text")
        text = p["content"]["text"]
        self.assertTrue(text.startswith("🚨"))
        self.assertIn("daily-report", text)
        self.assertIn("2026-11-19 08:30:00", text)
        self.assertIn("残差 12.5", text)

    def test_dry_run不联网(self):
        p = nf.build_payload("测试", ["a"])
        r = nf.send(p, dry_run=True)
        self.assertEqual(r["dry_run"], True)
        self.assertEqual(r["sent"], False)
        self.assertIsNone(r["error"])

    def test_只报非OK项(self):
        health = {"exit_code": 2, "results": [
            {"name": "数据新鲜度", "level": "OK", "detail": "最新 2026-11-30"},
            {"name": "对账残差", "level": "CRIT", "detail": "残差 9.00 超过容差 1.00"},
        ]}
        p = nf.alert_from_healthcheck(health)
        text = p["content"]["text"]
        self.assertIn("对账残差", text)
        self.assertNotIn("数据新鲜度", text)


if __name__ == "__main__":
    unittest.main()
