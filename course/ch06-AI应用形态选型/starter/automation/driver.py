"""页面驱动抽象：把"真实浏览器"和"流程逻辑"隔开。

为什么这么设计（呼应讲义 6.6）：
  浏览器自动化真正难的不是"点页面"，而是**流程编排 + 重试 + 证据留存**。
  这三件事和真实浏览器无关，可以用假驱动测；
  真实 Playwright 只负责实现 Page 这几个方法。

所以：
  Page      → 协议（真实实现用 Playwright，本文件提供 FakePage）
  FakePage  → 确定性假页面，可以模拟超时、记录调用、返回固定 HTML
"""

from __future__ import annotations

import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class PageError(RuntimeError):
    """页面操作失败（元素超时、点击失败、下载失败）。"""


class Page(Protocol):
    def goto(self, url: str) -> None: ...
    def wait_for(self, selector: str, timeout_ms: int) -> None: ...
    def download(self, selector: str, dest: Path) -> None: ...
    def screenshot(self, path: Path) -> None: ...
    def html(self) -> str: ...


@dataclass
class FakePage:
    """假页面：可配置哪些选择器会超时、超时几次。

    fail_selectors: 会失败的选择器
    fail_times:     连续失败几次后才成功（999 表示一直失败）
    """

    fail_selectors: tuple[str, ...] = ()
    fail_times: int = 999
    page_html: str = "<html><body>fake</body></html>"
    calls: list[tuple] = field(default_factory=list)
    attempts: Counter = field(default_factory=Counter)

    def goto(self, url: str) -> None:
        self.calls.append(("goto", url))

    def wait_for(self, selector: str, timeout_ms: int) -> None:
        self.calls.append(("wait_for", selector, timeout_ms))
        self.attempts[selector] += 1
        if selector in self.fail_selectors and self.attempts[selector] <= self.fail_times:
            raise PageError(f"元素超时：{selector}（{timeout_ms}ms）")

    def download(self, selector: str, dest: Path) -> None:
        self.calls.append(("download", selector, str(dest)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f"fake report for {selector}\n", encoding="utf-8")

    def screenshot(self, path: Path) -> None:
        self.calls.append(("screenshot", str(path)))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n(fake)")

    def html(self) -> str:
        self.calls.append(("html",))
        return self.page_html

    # ---- 断言辅助
    def count(self, action: str) -> int:
        return sum(1 for c in self.calls if c[0] == action)


def copy_tree(src: Path, dst: Path) -> None:
    """小工具：把证据目录整体搬走（测试里用）。"""
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
