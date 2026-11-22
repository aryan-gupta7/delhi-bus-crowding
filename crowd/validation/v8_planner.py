"""V8-lite: planner robustness on 200 random queries (answered share, crashes, latency, card mix)."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from crowd.planner.service import Planner
from crowd.validation.queries import Query


def run_v8(planner: Planner, queries: list[Query], day_type: str = "weekday") -> pd.DataFrame:
    """One row per query: latency, whether options were found, and which cards were shown."""
    rows = []
    for q in queries:
        t0 = time.perf_counter()
        try:
            out = planner.plan(q.from_stop, q.to_stop, q.time, day_type)
            error = ""
        except Exception as exc:                      # a crash is a result to report, not to hide
            out, error = {"cards": {}}, f"{type(exc).__name__}: {exc}"
        ev = out.get("evidence") or {}
        rows.append({"hour": q.hour, "latency_s": time.perf_counter() - t0, "answered": bool(out["cards"]),
                     "comfortable_shown": "comfortable" in out["cards"], "gamma_star": ev.get("gamma_star"),
                     "error": error})
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    """The V8 headline numbers."""
    return pd.DataFrame([{
        "queries": len(df), "answered": float(df["answered"].mean()), "crashes": int((df["error"] != "").sum()),
        "comfortable card shown": float(df["comfortable_shown"].mean()),
        "latency p50 (s)": float(np.percentile(df["latency_s"], 50)), "latency p95 (s)": float(np.percentile(df["latency_s"], 95)),
    }])
