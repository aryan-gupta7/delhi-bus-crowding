"""Stage runner: a tiny DAG with content-addressed caching and the run manifest.

A stage is a function ``fn(ctx)`` that reads named artefacts from the store and writes others.
It is skipped when its outputs exist and its *key* (config sections + source of its modules +
hashes of its inputs) is unchanged. The manifest records input/output hashes, the config hash,
stage keys and timings; the reproducibility hash covers data files and config only, never
timings.
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from crowd import __version__
from crowd.config import Config
from crowd.store import Store, sha256_file

log = logging.getLogger("crowd")
PACKAGE_DIR = Path(__file__).resolve().parent
KEYS_FILE = "stage_keys.json"
MANIFEST = "run_manifest.json"


@dataclass(frozen=True)
class Stage:
    name: str
    fn: Callable[["Context"], None]
    needs: tuple[str, ...]            # artefact file names, or "raw:tickets" / "raw:gtfs"
    makes: tuple[str, ...]            # artefact file names
    config: tuple[str, ...]           # top-level config sections that affect the stage
    modules: tuple[str, ...]          # crowd/<module>.py files whose source affects the stage


@dataclass
class Context:
    """What a stage may use: config, store, and an in-process cache of built objects."""

    cfg: Config
    store: Store
    cache: dict[str, Any] = field(default_factory=dict)

    def memo(self, key: str, factory: Callable[[], Any]) -> Any:
        if key not in self.cache:
            self.cache[key] = factory()
        return self.cache[key]

    def raw_path(self, name: str) -> Path:
        return self.cfg.path("tickets" if name == "raw:tickets" else "gtfs")

    def fingerprint(self, name: str) -> str:
        """Cheap, change-sensitive identity of an input (stat-based for raw files)."""
        if name.startswith("raw:"):
            p = self.raw_path(name)
            files = [p] if p.is_file() else sorted(p.glob("*.txt"))
            return hashlib.sha256("|".join(f"{f.name}:{f.stat().st_size}:{f.stat().st_mtime_ns}" for f in files).encode()).hexdigest()
        return self.store.sha256(name)


def _source_hash(modules: tuple[str, ...]) -> str:
    h = hashlib.sha256()
    for m in modules:
        h.update((PACKAGE_DIR / f"{m}.py").read_bytes())
    return h.hexdigest()


def stage_key(stage: Stage, ctx: Context) -> str:
    parts = {"config": ctx.cfg.hash(*stage.config), "code": _source_hash(stage.modules),
             "inputs": [ctx.fingerprint(n) for n in stage.needs]}
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


def run(stages: list[Stage], ctx: Context, force: bool = False, only: str | None = None) -> dict[str, float]:
    """Run stages in order, skipping those whose key is unchanged. Returns stage timings."""
    keys = ctx.store.read_json(KEYS_FILE) if ctx.store.exists(KEYS_FILE) else {}
    timings: dict[str, float] = {}
    for stage in stages:
        if only is not None and stage.name != only:
            continue
        key = stage_key(stage, ctx)
        fresh = keys.get(stage.name) == key and all(ctx.store.exists(m) for m in stage.makes)
        if fresh and not force:
            log.info("stage %-12s up to date", stage.name)
            continue
        log.info("stage %-12s running", stage.name)
        t0 = time.perf_counter()
        stage.fn(ctx)
        timings[stage.name] = round(time.perf_counter() - t0, 2)
        keys[stage.name] = key
        ctx.store.write_json(KEYS_FILE, keys)
        log.info("stage %-12s done in %.1fs", stage.name, timings[stage.name])
    return timings


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                              cwd=PACKAGE_DIR.parent).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write_manifest(stages: list[Stage], ctx: Context, timings: dict[str, float], extra: dict[str, Any]) -> dict:
    """Write run_manifest.json. ``reproducibility_hash`` covers config and data outputs only."""
    outputs = sorted({m for s in stages for m in s.makes})
    out_hashes = {m: ctx.store.sha256(m) for m in outputs if ctx.store.exists(m)}
    inputs = {n: sha256_file(ctx.raw_path(n)) if ctx.raw_path(n).is_file() else
              {f.name: sha256_file(f) for f in sorted(ctx.raw_path(n).glob("*.txt"))}
              for n in ("raw:tickets", "raw:gtfs")}
    repro = hashlib.sha256(json.dumps({"config": ctx.cfg.hash(), "outputs": out_hashes},
                                      sort_keys=True).encode()).hexdigest()
    manifest = {
        "reproducibility_hash": repro, "config_hash": ctx.cfg.hash(), "inputs": inputs,
        "outputs": out_hashes, "git_commit": _git_commit(), "package_version": __version__,
        "python": platform.python_version(), **extra,
        "timings": timings,                    # unhashed block
    }
    ctx.store.write_json(MANIFEST, manifest)
    return manifest
