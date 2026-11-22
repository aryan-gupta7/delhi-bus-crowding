"""S0b: which days and hours count (design/mechanism.md S0, business-logic.md §2).

The rule is data-driven: day-type first, two ticket streams (NULL-vehicle / tagged) checked
against the median of their own day-type, a stream-fault test, and an hour mask with a count
floor. The thresholds were chosen on October to reproduce its known anomalies, so passing
gate G1 is a regression test of the rule, not evidence that it generalises.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd.config import Config

WEEKDAY, WEEKEND = "weekday", "weekend"
DAY_TYPES = (WEEKDAY, WEEKEND)


def _stream_hour_volumes(tickets: pd.DataFrame, days: np.ndarray) -> np.ndarray:
    """Dense passenger volumes ``V[stream, day, hour]``; stream 0 = NULL vehicle, 1 = tagged."""
    day_idx = np.searchsorted(days, tickets["date"].to_numpy())
    stream = tickets["vehicle"].notna().to_numpy().astype(np.int64)
    flat = (stream * len(days) + day_idx) * 24 + tickets["hour"].to_numpy().astype(np.int64)
    vol = np.bincount(flat, weights=tickets["pax"].to_numpy(), minlength=2 * len(days) * 24)
    return vol.reshape(2, len(days), 24)


def build_day_hour_ok(tickets: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """One row per (date, hour) with its day-type, eligibility flags and the reason."""
    ecfg = cfg.eligibility
    days = np.sort(tickets["date"].unique())
    dow = pd.DatetimeIndex(days).dayofweek.to_numpy()
    vol = _stream_hour_volumes(tickets, days)                 # [2, D, 24]
    day_total = vol.sum(axis=(0, 2))

    # 1. day-type first
    r_day = day_total / np.median(day_total[dow < 5])
    is_weekend = (dow >= 5) | (r_day < ecfg.holiday_ratio)
    day_type = np.where(is_weekend, WEEKEND, WEEKDAY)

    # 2-3. per-stream ratios against the day-type's own medians
    stream_day = vol.sum(axis=2)                              # [2, D]
    day_ratio = np.zeros_like(stream_day, dtype=float)
    hour_masked = np.zeros(vol.shape, dtype=bool)
    for dt in (WEEKDAY, WEEKEND):
        sel = day_type == dt
        if not sel.any():
            continue
        for s in range(2):
            med_day = np.median(stream_day[s, sel])
            day_ratio[s, sel] = stream_day[s, sel] / med_day if med_day > 0 else np.nan
            med_hour = np.median(vol[s, sel, :], axis=0)      # [24]
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = vol[s, sel, :] / med_hour
            decided = med_hour >= ecfg.min_median            # P-M12: no decision on tiny medians
            hour_masked[s, sel, :] = decided[None, :] & (ratio < ecfg.mask_ratio)

    # 4. stream-fault day: the two streams disagree about how busy the day was
    hi, lo = day_ratio.max(axis=0), day_ratio.min(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        fault = np.where(hi > 0, lo / hi, 1.0) < ecfg.stream_fault_ratio

    # 5-6. drop the whole (day, hour) when either stream is masked; whole day on a fault
    outage = hour_masked.any(axis=0)                          # [D, 24]
    hour_ok = ~outage & ~fault[:, None]
    reason = np.where(fault[:, None], "stream_fault", np.where(outage, "outage", "ok"))

    d_idx, h_idx = np.meshgrid(np.arange(len(days)), np.arange(24), indexing="ij")
    return pd.DataFrame({
        "date": days[d_idx.ravel()],
        "hour": h_idx.ravel().astype("int8"),
        "day_type": day_type[d_idx.ravel()],
        "day_ok": (~fault)[d_idx.ravel()],
        "hour_ok": hour_ok.ravel(),
        "reason": reason.ravel(),
        "v_null": vol[0].ravel().astype("int32"),
        "v_tagged": vol[1].ravel().astype("int32"),
    })
