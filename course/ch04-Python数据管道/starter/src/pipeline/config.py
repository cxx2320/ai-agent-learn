"""配置加载。

契约（tests 依赖它，别改签名）：
    load_config(path) -> Config
    - path 指向 settings.yaml
    - settings.yaml 里的相对路径，相对「项目根目录」解析
      项目根目录 = settings.yaml 的上两级（config/ 的父目录）
    - 缺失的键用 DEFAULTS 补，未知的键忽略
    - 环境变量里的密钥不要写进 Config 的 repr（用 field(repr=False)）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULTS = {
    "data_dir": "./data",
    "out_dir": "./output",
    "log_dir": "./logs",
    "site_offset_from_bj_hours": -16,
    "reconcile_tolerance_usd": 1.00,
    "thresholds": {
        "acos_warn": 0.35,
        "refund_rate_warn": 0.08,
        "doi_warn": 7,
        "ad_zero_order_spend_usd": 80,
    },
}


@dataclass(frozen=True)
class Config:
    root: Path
    data_dir: Path
    out_dir: Path
    log_dir: Path
    site_offset_from_bj_hours: int
    tolerance_usd: float
    thresholds: dict
    llm_api_key: str = field(default="", repr=False)   # 密钥不进日志


def load_config(path: str | Path) -> Config:
    """读 YAML → Config。任何路径都必须解析成绝对路径。

    提示：
      import yaml
      root = Path(path).resolve().parent.parent
      cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
      merged = {**DEFAULTS, **cfg}          # 浅合并足够；thresholds 记得整体替换
    """
    raise NotImplementedError("TODO: 实现 load_config（见上方契约与提示）")
