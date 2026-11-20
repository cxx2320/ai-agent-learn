"""配置加载（参考实现）。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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
    llm_api_key: str = field(default="", repr=False)


def _resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (root / p).resolve()


def load_config(path: str | Path) -> Config:
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(str(p))

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    merged = {**DEFAULTS, **raw}
    root = p.parent.parent          # settings.yaml 在 config/ 下，项目根是上一级

    thresholds = dict(DEFAULTS["thresholds"])
    thresholds.update(merged.get("thresholds") or {})

    return Config(
        root=root,
        data_dir=_resolve(root, merged["data_dir"]),
        out_dir=_resolve(root, merged["out_dir"]),
        log_dir=_resolve(root, merged["log_dir"]),
        site_offset_from_bj_hours=int(merged["site_offset_from_bj_hours"]),
        tolerance_usd=float(merged["reconcile_tolerance_usd"]),
        thresholds=thresholds,
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
    )
