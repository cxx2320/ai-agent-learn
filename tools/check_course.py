"""课程一致性检查器。

为什么需要它：这套教程有 127 个文件、大量交叉引用，手工维护必然出错。
我已经犯过两次错——把 9 个测试写成 8 个。这类错误不会让代码崩，只会让学员困惑。

检查五件事：
  1. 每章是否有 讲义 / 练习 / 答案 三个文件
  2. markdown 里的相对链接是否存在（断链）
  3. 文档里声称的"N 个测试"是否与 tests/ 下真实的 def test_ 数量一致
  4. README 里的测试总数与实测总数是否一致
  5. 带代码的章节是否都有可运行入口 run.py

用法：
    python tools/check_course.py
    python tools/check_course.py --json

退出码：0 全部通过 / 1 有问题
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COURSE = ROOT / "course"

REQUIRED_FILES = ("讲义.md", "练习与自测.md", "答案与批改要点.md")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# 只校验"整套测试"的声称，避免把"其中 6 个测试覆盖循环"这类子集描述误判
TEST_CLAIM_RE = re.compile(r"(\d+)\s*个测试(?:全绿|，应全绿)")
RAN_RE = re.compile(r"Ran (\d+) tests")
TEST_DEF_RE = re.compile(r"^\s*def test_", re.M)


def chapter_dirs() -> list[Path]:
    return sorted(p for p in COURSE.iterdir() if p.is_dir() and p.name.startswith("ch"))


def count_tests(d: Path) -> int | None:
    """一章的测试数。优先取 solution/tests（参考实现），其次 starter/tests。"""
    for sub in ("solution/tests", "starter/tests", "tests"):
        tests = d / sub
        if tests.is_dir():
            n = 0
            for f in tests.rglob("*.py"):
                n += len(TEST_DEF_RE.findall(f.read_text(encoding="utf-8", errors="ignore")))
            return n
    return None


def md_files() -> list[Path]:
    return sorted(COURSE.rglob("*.md")) + ([ROOT / "README.md"] if (ROOT / "README.md").exists() else [])


def check_required_files() -> list[str]:
    issues = []
    for d in chapter_dirs():
        for name in REQUIRED_FILES:
            if not (d / name).exists():
                issues.append(f"[缺文件] {d.name}/{name}")
    return issues


def check_links() -> list[str]:
    issues = []
    for f in md_files():
        text = f.read_text(encoding="utf-8", errors="ignore")
        for raw in LINK_RE.findall(text):
            target = raw.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.strip("<>")
            target = target.split("#")[0]
            if not target:
                continue
            resolved = (f.parent / target).resolve()
            if not resolved.exists():
                issues.append(f"[断链] {f.relative_to(ROOT)} → {target}")
    return issues


def check_test_claims() -> list[str]:
    """文档里声称的"整套测试数"必须与该章 tests/ 的真实数量一致。"""
    issues = []
    for d in chapter_dirs():
        actual = count_tests(d)
        if actual is None:
            continue
        for f in d.glob("*.md"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            claims = set(TEST_CLAIM_RE.findall(text)) | set(RAN_RE.findall(text))
            for claim in claims:
                if int(claim) != actual:
                    issues.append(
                        f"[数字不符] {d.name}/{f.name} 写 '{claim} 个测试'，实际 {actual} 个")
    return issues


def check_readme_total() -> tuple[list[str], int]:
    issues = []
    total = 0
    per_chapter = {}
    for d in chapter_dirs():
        n = count_tests(d)
        if n is not None:
            per_chapter[d.name] = n
            total += n

    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        # 只校验"总共 N 个测试"这句总账，避免把"9 个测试全绿"这类章节描述误判
        for claim in set(re.findall(r"总共\s*\**(\d+)\s*个测试", text)):
            if int(claim) != total:
                issues.append(f"[数字不符] README.md 写 '总共 {claim} 个测试'，实际合计 {total} 个")
        # 表格逐章校验：| ch04 | 9 个 | ...
        for name, n in per_chapter.items():
            short = name[:4]
            m = re.search(rf"\|\s*{short}\s*\|\s*(\d+)\s*个", text)
            if m and int(m.group(1)) != n:
                issues.append(f"[数字不符] README.md 表格 {short} 写 {m.group(1)} 个，实际 {n} 个")
            elif not m:
                issues.append(f"[缺行] README.md 表格没有 {short} 的测试数")
    return issues, total


def check_entrypoints() -> list[str]:
    issues = []
    for d in chapter_dirs():
        if (d / "starter").is_dir() or (d / "solution").is_dir():
            for sub in ("starter", "solution"):
                p = d / sub
                if p.is_dir() and not (p / "run.py").exists():
                    issues.append(f"[缺入口] {d.name}/{sub}/run.py")
    return issues


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_course", description="课程一致性检查")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    issues: list[str] = []
    issues += check_required_files()
    issues += check_links()
    issues += check_test_claims()
    total_issues, total_tests = check_readme_total()
    issues += total_issues
    issues += check_entrypoints()

    if a.json:
        print(json.dumps({"issues": issues, "total_tests": total_tests}, ensure_ascii=False, indent=2))
    else:
        chapters = chapter_dirs()
        print(f"检查范围：{len(chapters)} 章，{len(md_files())} 个 markdown 文件")
        print(f"测试合计：{total_tests} 个")
        if not issues:
            print("\n✅ 全部通过：文件齐全、无断链、数字一致")
        else:
            print(f"\n❌ 发现 {len(issues)} 个问题：")
            for i in issues:
                print("  " + i)
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
