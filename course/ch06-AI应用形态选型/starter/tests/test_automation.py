"""浏览器自动化的验收测试：7 个。用假页面驱动，不启动真实浏览器。

测试目标不是"会不会点页面"，而是**流程编排与稳定性**：
重试次数、单站点失败隔离、失败证据留存、参数传递、幂等覆盖。
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automation.driver import FakePage, PageError            # noqa: E402
from automation.task import SiteTask, download_sites, pick_selector   # noqa: E402

TASKS = [
    SiteTask("US", "https://example.com/us", ("[data-testid=dl]",), "us.csv"),
    SiteTask("UK", "https://example.com/uk", ("[data-testid=dl]",), "uk.csv"),
]


def tmpdir(name: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"ch06-auto-{name}-"))


class TestDownload(unittest.TestCase):
    def test_全部成功(self):
        page = FakePage()
        out, ev = tmpdir("ok"), tmpdir("ok-ev")
        r = download_sites(page, TASKS, out, ev)
        self.assertTrue(r.all_ok)
        self.assertEqual(r.ok, ["US", "UK"])
        self.assertEqual(r.attempts, 2)
        self.assertTrue((out / "us.csv").exists())
        self.assertTrue((out / "uk.csv").exists())

    def test_超时重试次数(self):
        page = FakePage(fail_selectors=("[data-testid=dl]",), fail_times=999)
        out, ev = tmpdir("retry"), tmpdir("retry-ev")
        r = download_sites(page, TASKS[:1], out, ev, retries=2)
        # 1 次正常 + 2 次重试 = 3 次尝试
        self.assertEqual(r.attempts, 3)
        self.assertEqual(r.failed[0]["tries"], 3)
        self.assertEqual(page.attempts["[data-testid=dl]"], 3)

    def test_失败时留存证据(self):
        page = FakePage(fail_selectors=("[data-testid=dl]",), fail_times=999)
        out, ev = tmpdir("ev"), tmpdir("ev2")
        download_sites(page, TASKS[:1], out, ev, retries=1)
        self.assertTrue((ev / "US.png").exists(), "应落盘截图")
        self.assertTrue((ev / "US.html").exists(), "应落盘 HTML")
        self.assertEqual(page.count("screenshot"), 1)

    def test_单站点失败不影响其他(self):
        # 只有 US 的选择器会超时
        page = FakePage(fail_selectors=("[data-testid=us]",), fail_times=999)
        tasks = [
            SiteTask("US", "https://example.com/us", ("[data-testid=us]",), "us.csv"),
            SiteTask("UK", "https://example.com/uk", ("[data-testid=uk]",), "uk.csv"),
        ]
        out, ev = tmpdir("mix"), tmpdir("mix-ev")
        r = download_sites(page, tasks, out, ev, retries=1)
        self.assertEqual(r.ok, ["UK"])
        self.assertEqual([f["site"] for f in r.failed], ["US"])
        self.assertTrue((out / "uk.csv").exists())

    def test_超时参数透传(self):
        page = FakePage()
        out, ev = tmpdir("to"), tmpdir("to-ev")
        download_sites(page, TASKS[:1], out, ev, timeout_ms=12_345)
        waits = [c for c in page.calls if c[0] == "wait_for"]
        self.assertEqual(waits[0][2], 12_345)

    def test_重跑覆盖不追加(self):
        page = FakePage()
        out, ev = tmpdir("idem"), tmpdir("idem-ev")
        download_sites(page, TASKS[:1], out, ev)
        download_sites(page, TASKS[:1], out, ev)
        self.assertEqual((out / "us.csv").read_text(encoding="utf-8").count("fake report"), 1)

    def test_没有选择器要报错(self):
        with self.assertRaises(ValueError):
            pick_selector(SiteTask("US", "u", (), "f.csv"))


if __name__ == "__main__":
    unittest.main()
