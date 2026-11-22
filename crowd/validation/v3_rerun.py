"""V3: rerun on new files. Same command, time-sliced ticket CSVs, thresholds frozen from the reference run.

Checks that the pipeline completes on a file it has never seen, that GTFS-only artefacts (patterns,
stretches) are bit-identical, that frozen cuts keep the levels comparable, and that a full rerun in a
fresh directory reproduces the reference hash. Slices are subsets of the reference data, so this tests
rerun determinism and constants leaking, not generalisation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from crowd.pipeline import Context, reproducibility_hash, run
from crowd.stages import STAGES
from crowd.store import Store
from crowd.validation import metrics

RUNNABLE = [s for s in STAGES if s.name != "gates"]
KEYS = ["route", "stretch_id", "hour"]


def _slice_csv(source: Path, target: Path, keep) -> None:
    """Write the rows of the raw CSV whose ``created_at`` date satisfies ``keep`` (same schema)."""
    raw = pd.read_csv(source, dtype=str, keep_default_na=False)
    raw[keep(raw["created_at"].str.slice(0, 10))].to_csv(target, index=False)


def _agreement(reference: pd.DataFrame, other: pd.DataFrame) -> tuple[int, float]:
    """Weighted kappa of weekday levels on cells that have an estimate in both runs."""
    a = reference[(reference["day_type"] == "weekday") & (reference["tier"] != "No estimate")]
    b = other[(other["day_type"] == "weekday") & (other["tier"] != "No estimate")]
    j = a.merge(b, on=KEYS, suffixes=("_ref", "_new"))
    kappa = metrics.weighted_kappa(j["level_ref"].to_numpy(int), j["level_new"].to_numpy(int),
                                   (j["pi_central_ref"] * j["Z_ref"]).to_numpy())
    return len(j), kappa


def run_v3(ctx: Context) -> pd.DataFrame:
    """One row per check."""
    ref, cfg = ctx.store, ctx.cfg
    frozen = ref.read_json("cuts.json")["cuts"]
    days = sorted(pd.to_datetime(ref.read_table("day_hour_ok.parquet", ["date"])["date"].unique()).strftime("%Y-%m-%d"))
    middle = days[len(days) // 2]
    rows = []
    with tempfile.TemporaryDirectory(prefix="crowd_v3_") as tmp:
        tmp = Path(tmp)
        slices = {"first half": lambda d: d < middle, "second half": lambda d: d >= middle}
        for name, keep in slices.items():
            csv = tmp / f"{name.replace(' ', '_')}.csv"
            _slice_csv(cfg.path("tickets"), csv, keep)
            cfg_slice = cfg.with_overrides({"paths.tickets": str(csv), "paths.out": str(tmp / f"out_{name.replace(' ', '_')}")})
            sctx = Context(cfg=cfg_slice, store=Store(cfg_slice.path("out")), cache={"frozen_cuts": frozen})
            run(RUNNABLE, sctx)
            n, kappa = _agreement(ref.read_table("crowding_cells.parquet"), sctx.store.read_table("crowding_cells.parquet"))
            same_gtfs = all(sctx.store.sha256(f) == ref.sha256(f) for f in ("patterns.parquet", "stretches.parquet", "segments.parquet"))
            rows += [
                {"check": f"{name}: pipeline completes on a new file", "result": "yes", "passed": True},
                {"check": f"{name}: GTFS-only artefacts (patterns, segments, stretches) bit-identical to the reference", "result": same_gtfs, "passed": same_gtfs},
                {"check": f"{name}: weekday level agreement with the reference (frozen cuts), weighted kappa on {n:,} cells",
                 "result": round(kappa, 3), "passed": bool(kappa > 0.4)},
            ]
        fresh_cfg = cfg.with_overrides({"paths.out": str(tmp / "out_fresh")})
        fresh = Context(cfg=fresh_cfg, store=Store(fresh_cfg.path("out")))
        run(RUNNABLE, fresh)
        same = reproducibility_hash(RUNNABLE, fresh)[0] == reproducibility_hash(RUNNABLE, ctx)[0]
        rows.append({"check": "full rerun in a fresh directory reproduces the reference reproducibility hash", "result": same, "passed": same})
    return pd.DataFrame(rows)
