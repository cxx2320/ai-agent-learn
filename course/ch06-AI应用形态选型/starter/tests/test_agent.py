"""Agent 验收测试：6 个。全部离线，不调模型。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.planner import ScriptedPlanner, build_demo_registry, loop_planner   # noqa: E402
from agent.react import run                                                     # noqa: E402


class TestAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = build_demo_registry()

    def test_两步正常完成(self):
        planner = ScriptedPlanner(
            [{"tool": "search_kb", "args": {"q": "退货 利润"}},
             {"tool": "calc", "args": {"expr": "3 * 29.99"}}],
            "退货会损失本金与配送费，3 单 89.97 美元。",
        )
        r = run("退货影响利润吗？3 单 29.99 是多少", planner, self.reg)
        self.assertIsNone(r["stopped"])
        self.assertEqual(r["steps"], 2)
        self.assertEqual(len(r["trace"]), 2)
        self.assertAlmostEqual(r["trace"][1]["result"], 89.97)
        self.assertIn("89.97", r["answer"])

    def test_未知工具不抛异常(self):
        planner = ScriptedPlanner(
            [{"tool": "delete_all_data", "args": {}}], "不会到这里")
        r = run("测试幻觉调用", planner, self.reg)
        self.assertFalse(r["trace"][0]["ok"])
        self.assertIn("unknown_tool", r["trace"][0]["error"])

    def test_缺参数返回错误码(self):
        planner = ScriptedPlanner([{"tool": "search_kb", "args": {}}], "结束")
        r = run("测试缺参数", planner, self.reg)
        self.assertIn("missing_param:q", r["trace"][0]["error"])

    def test_重复调用触发刹车(self):
        planner = loop_planner("calc", {"expr": "1+1"})
        r = run("死循环测试", planner, self.reg)
        self.assertEqual(r["stopped"], "repeat")
        self.assertIn("重复调用", r["answer"])
        self.assertLessEqual(r["steps"], 3)      # 1 次正常 + 再 2 次即判定

    def test_超过最大步数停止(self):
        # 每步参数都不同，绕开重复检测，只能靠步数上限刹车
        actions = [{"tool": "calc", "args": {"expr": f"{i}+1"}} for i in range(20)]
        r = run("步数上限测试", ScriptedPlanner(actions, "done"), self.reg, max_steps=5)
        self.assertEqual(r["stopped"], "max_steps")
        self.assertEqual(r["steps"], 5)

    def test_trace完整可排查(self):
        planner = ScriptedPlanner([{"tool": "calc", "args": {"expr": "2*3"}}], "12")
        r = run("trace 测试", planner, self.reg)
        step = r["trace"][0]
        for key in ("step", "tool", "args", "ok", "result"):
            self.assertIn(key, step)
        self.assertEqual(step["tool"], "calc")


if __name__ == "__main__":
    unittest.main()
