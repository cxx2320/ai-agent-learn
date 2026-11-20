"""切分（chunking）：RAG 里最容易被低估、也最决定效果的一步。

切得好，检索命中率高；切得烂，模型拿到的是一堆没头没尾的碎片。
本实现按 markdown 的 `## ` 小节切分，过长再按段落切，并保留来源与章节名。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAX_CHARS = 400      # 单块上限
OVERLAP = 60         # 过长小节切分时的重叠字符数


@dataclass
class Chunk:
    doc: str          # 来源文件名
    section: str      # 所属小节标题
    text: str


def _strip_front_matter(raw: str) -> str:
    """去掉开头的 YAML front matter（--- ... ---）。"""
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) == 3:
            return parts[2]
    return raw


def _split_long(text: str, limit: int = MAX_CHARS, overlap: int = OVERLAP) -> list[str]:
    if len(text) <= limit:
        return [text]
    out, start = [], 0
    while start < len(text):
        out.append(text[start:start + limit])
        if start + limit >= len(text):
            break
        start += limit - overlap
    return out


def load_docs(corpus_dir) -> list[Chunk]:
    """读目录下所有 .md，切成 Chunk 列表。

    契约（tests 依赖）：
      - 每个 chunk 的 text 长度 <= MAX_CHARS
      - doc 是文件名（如 "amazon-fba-fees.md"），不是绝对路径
      - section 是 `## ` 后的标题；没有小节的文档用文档标题（`# `）兜底
      - front matter 不进 chunk
      - 返回按 (doc, 出现顺序) 稳定排序
    """
    chunks: list[Chunk] = []
    for path in sorted(Path(corpus_dir).glob("*.md")):
        body = _strip_front_matter(path.read_text(encoding="utf-8"))
        title = path.stem
        section = title
        buf: list[str] = []

        def flush():
            text = "\n".join(buf).strip()
            buf.clear()
            if not text:
                return
            for piece in _split_long(text):
                chunks.append(Chunk(doc=path.name, section=section, text=piece.strip()))

        for line in body.splitlines():
            if line.startswith("# ") and not line.startswith("## "):
                title = line[2:].strip()
                section = title
                continue
            if line.startswith("## "):
                flush()
                section = line[3:].strip()
                continue
            buf.append(line)
        flush()
    return chunks
