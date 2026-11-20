"""零安装入口：不用装包，直接跑。

    python run.py --help
    python run.py --start 2026-11-01 --end 2026-11-30

为什么不用 `python -m pipeline.main`：那要求 src 在 sys.path 里。
真做项目时会配 pyproject.toml + `pip install -e .`，本章先用这 4 行省掉安装步骤。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pipeline.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
