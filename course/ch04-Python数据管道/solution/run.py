"""零安装入口：不用装包，直接跑。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pipeline.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
