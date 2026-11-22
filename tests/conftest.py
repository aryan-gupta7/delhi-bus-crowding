"""Shared fixtures: the real config, and the mini world run through the whole pipeline once."""

from __future__ import annotations

from pathlib import Path

import pytest

from crowd.config import Config
from crowd.pipeline import Context, run
from crowd.stages import STAGES
from crowd.store import Store
from tests import mini

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def real_config() -> Config:
    return Config.load(ROOT / "config.yaml")


@pytest.fixture(scope="session")
def mini_ctx(tmp_path_factory, real_config) -> Context:
    """Pipeline stages S0-S8 run on the mini world (everything except the real-data-only gates)."""
    root = tmp_path_factory.mktemp("mini")
    cfg = mini.build(root, real_config)
    ctx = Context(cfg=cfg, store=Store(cfg.path("out")))
    run([s for s in STAGES if s.name != "gates"], ctx)
    return ctx
