"""验收标准：9 个测试（RAG 部分）。全部离线，不需要 API Key。

跑法：
    cd starter
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kb import answer as ans          # noqa: E402
from kb import chunk as ck            # noqa: E402
from kb import retrieve as rt         # noqa: E402

CORPUS = ROOT / "corpus"


class TestChunk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = ck.load_docs(CORPUS)

    def test_块长度不超上限(self):
        self.assertTrue(self.chunks)
        for c in self.chunks:
            self.assertLessEqual(len(c.text), ck.MAX_CHARS, msg=f"{c.doc} 超长")

    def test_覆盖全部文档(self):
        docs = {c.doc for c in self.chunks}
        expected = {p.name for p in CORPUS.glob("*.md")}
        self.assertEqual(docs, expected)

    def test_不带_front_matter(self):
        for c in self.chunks:
            self.assertNotIn("effective_date", c.text)
            self.assertFalse(c.text.startswith("---"))


class TestRetrieve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = ck.load_docs(CORPUS)
        cls.index = rt.build_index(cls.chunks)

    def test_仓储费问题命中费用文档(self):
        hits = rt.search(self.index, "月度仓储费怎么算")
        self.assertTrue(hits, "应该能检索到内容")
        self.assertEqual(hits[0][0].doc, "amazon-fba-fees.md")
        # 文档对了还不够：提问问的是"月度"，排第一的必须是对应小节
        self.assertIn("月度仓储费", hits[0][0].section)
        self.assertIn("仓储", hits[0][0].text)

    def test_无关问题返回空(self):
        hits = rt.search(self.index, "今天天气怎么样")
        self.assertEqual(hits, [], "无关问题必须返回空，否则会开始编")

    def test_中文分词是双字(self):
        self.assertIn("仓储", rt.tokenize("月度仓储费"))
        self.assertNotIn("月度仓储费", rt.tokenize("月度仓储费"))


class TestAnswer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = ck.load_docs(CORPUS)
        cls.index = rt.build_index(cls.chunks)

    def test_有命中时带引用(self):
        hits = rt.search(self.index, "退货窗口是多少天")
        result = ans.answer("退货窗口是多少天", hits)
        self.assertGreaterEqual(len(result.citations), 1)
        self.assertIn("amazon-returns.md", [c["doc"] for c in result.citations])

    def test_无命中时拒答(self):
        hits = rt.search(self.index, "今天天气怎么样")
        result = ans.answer("今天天气怎么样", hits)
        self.assertEqual(result.citations, [])
        self.assertIn("没有找到", result.text)

    def test_引用可追溯(self):
        valid_docs = {p.name for p in CORPUS.glob("*.md")}
        for q in ("佣金怎么算", "VAT 怎么申报", "ACOS 是什么"):
            hits = rt.search(self.index, q)
            result = ans.answer(q, hits)
            for c in result.citations:
                self.assertIn(c["doc"], valid_docs)
                self.assertTrue(c["section"])
                self.assertGreater(c["score"], 0)


if __name__ == "__main__":
    unittest.main()
