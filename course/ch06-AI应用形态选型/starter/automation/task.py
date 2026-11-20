"""下载任务编排：稳定性四件套的落地。

① 显式等待元素（不 sleep）
② 选择器候选链（data-testid > id > text）
③ 失败截图 + HTML 落盘
④ 登录态复用（本文件只留钩子，真实实现见文档）
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .driver import Page, PageError


@dataclass
class SiteTask:
    name: str                 # 站点名，如 "US"
    url: str                  # 报表页地址
    selectors: tuple[str, ...]   # 选择器候选链，按优先级排列
    filename: str             # 下载后的文件名


@dataclass
class DownloadResult:
    ok: list[str]
    failed: list[dict]
    attempts: int

    @property
    def all_ok(self) -> bool:
        return not self.failed


def pick_selector(task: SiteTask) -> str:
    """选择器候选链的第一个。真实实现会在运行时逐个试。"""
    if not task.selectors:
        raise ValueError(f"{task.name}: 没有配置选择器")
    return task.selectors[0]


def download_sites(page: Page, tasks: list[SiteTask], out_dir: Path,
                   evidence_dir: Path, *, retries: int = 2,
                   timeout_ms: int = 30_000) -> DownloadResult:
    """逐个站点下载。

    关键行为（tests 依赖）：
      - 每个站点失败最多重试 retries 次（总尝试 = retries + 1）
      - **单个站点失败不影响其他站点**（继续下一个）
      - 最终失败时：截图 + HTML 落盘到 evidence_dir，文件名用站点名
      - 返回值里 ok 是成功的站点名，failed 是 {site, error, tries}
    """
    out_dir = Path(out_dir)
    evidence_dir = Path(evidence_dir)
    ok: list[str] = []
    failed: list[dict] = []
    attempts_total = 0

    for task in tasks:
        selector = pick_selector(task)
        last_error = ""
        for attempt in range(1, retries + 2):
            attempts_total += 1
            try:
                page.goto(task.url)
                page.wait_for(selector, timeout_ms)
                page.download(selector, out_dir / task.filename)
                ok.append(task.name)
                last_error = ""
                break
            except PageError as exc:
                last_error = str(exc)
                if attempt == retries + 1:
                    page.screenshot(evidence_dir / f"{task.name}.png")
                    (evidence_dir / f"{task.name}.html").write_text(
                        page.html(), encoding="utf-8")
                    failed.append({"site": task.name, "error": last_error,
                                   "tries": attempt})

    return DownloadResult(ok=ok, failed=failed, attempts=attempts_total)
