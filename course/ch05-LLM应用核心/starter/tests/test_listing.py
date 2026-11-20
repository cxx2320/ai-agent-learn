"""验收标准：9 个测试。全部**不联网**，用 mock 语义。

跑法：
    cd starter
    python -m unittest discover -s tests -v
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listing import evaluate, llm, prompt, schema          # noqa: E402

GOOD = {
    "title": ("Wireless Charger Stand, 15W Fast Charging Station for iPhone and Samsung, "
              "Foldable Desk Charger with Non-Slip Base, Black"),
    "bullets": [
        "3-IN-1 CHARGING: charge your phone, wireless earbuds and smartwatch together on one compact desk stand, so you can replace three separate chargers with a single tidy setup.",
        "15W FAST CHARGE: delivers full-speed wireless charging for iPhone and Samsung devices, with built-in over-heat protection that keeps the charging speed stable all night long.",
        "FOLDABLE AND PORTABLE: the adjustable stand folds flat in seconds, which makes it easy to pack in a backpack, carry in a tote bag or store in a desk drawer when you travel.",
        "NON-SLIP BASE: silicone pads under the stand keep the charger steady on glass, wood and metal desks, so your phone will not slide or fall while you are working or watching videos.",
        "CLEAN DESK SETUP: keeps charging cables off the table, gives you a tidy and organized workspace, and lets you answer calls or check notifications without unplugging anything at all.",
    ],
    "search_terms": ["wireless charger stand", "charging station", "desk charger"],
}


def load_products():
    import csv
    with open(ROOT / "data" / "products.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.products = load_products()
        cls.p = cls.products[0]

    def test_合法输出通过校验(self):
        self.assertEqual(schema.validate_listing(GOOD, self.p), [])

    def test_六条五点被拒(self):
        bad = dict(GOOD, bullets=GOOD["bullets"] + ["AN EXTRA POINT: " + "x" * 130])
        self.assertIn(schema.RULE_BULLETS_5, schema.validate_listing(bad, self.p))

    def test_中文标题被拒(self):
        bad = dict(GOOD, title=GOOD["title"] + " 无线充电")
        self.assertIn(schema.RULE_TITLE_EN, schema.validate_listing(bad, self.p))

    def test_禁用词被拒(self):
        bad = dict(GOOD, bullets=[GOOD["bullets"][0].replace("3-IN-1", "BEST 3-IN-1")] + GOOD["bullets"][1:])
        self.assertIn(schema.RULE_FORBIDDEN, schema.validate_listing(bad, self.p))

    def test_解析带代码块的JSON(self):
        raw = "好的，这是结果：\n```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```\n希望有帮助"
        self.assertEqual(schema.parse_json(raw)["title"], GOOD["title"])


class TestMockPipeline(unittest.TestCase):
    def test_mock对全部产品都合法(self):
        template = prompt.load_template(ROOT / "prompts" / "listing_v1.txt")
        for p in load_products():
            msgs = prompt.build_messages(p, template)
            res = llm.complete(msgs, mock=True)
            data = schema.parse_json(res.text)
            self.assertEqual(schema.validate_listing(data, p), [], msg=f"{p['asin']} 不合规")

    def test_mock幂等(self):
        template = prompt.load_template(ROOT / "prompts" / "listing_v1.txt")
        p = load_products()[0]
        a = llm.complete(prompt.build_messages(p, template), mock=True).text
        b = llm.complete(prompt.build_messages(p, template), mock=True).text
        self.assertEqual(a, b)


class TestEvaluate(unittest.TestCase):
    def test_满分与汇总(self):
        p = load_products()[0]
        score, failed = evaluate.score_listing(GOOD, p)
        self.assertEqual(score, 1.0)
        self.assertEqual(failed, [])

        report = evaluate.summarize([
            {"asin": "A", "ok": True, "score": 1.0, "failed": [],
             "cost_cny": 0.001, "elapsed_s": 2.0, "attempts": 1},
            {"asin": "B", "ok": False, "score": 0.71, "failed": [schema.RULE_TITLE_LEN],
             "cost_cny": 0.002, "elapsed_s": 4.0, "attempts": 2},
        ])
        self.assertAlmostEqual(report["pass_rate"], 0.5)
        self.assertAlmostEqual(report["total_cost_cny"], 0.003)
        self.assertEqual(report["failed_rules"][schema.RULE_TITLE_LEN], 1)


class TestCost(unittest.TestCase):
    def test_成本计算(self):
        # 100 万输入 + 100 万输出，deepseek-chat：1 + 2 = 3 元
        self.assertAlmostEqual(llm.estimate_cost("deepseek-chat", 1_000_000, 1_000_000), 3.0)


if __name__ == "__main__":
    unittest.main()
