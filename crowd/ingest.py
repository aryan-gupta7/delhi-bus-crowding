"""S0a: raw ticket CSV -> typed ticket table."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

TICKET_COLUMNS = [
    "tid", "ts", "date", "hour", "dow", "minute_of_day", "route", "vehicle",
    "is_ac", "pax", "amount", "start_name", "end_name",
]


@dataclass
class IngestReport:
    rows_in: int
    rows_out: int
    dropped_bad_timestamp: int
    dropped_bad_pax: int
    exact_duplicates_kept: int
    total_pax: int
    null_vehicle_share: float


def read_tickets(csv_path: Path) -> tuple[pd.DataFrame, IngestReport]:
    """Parse the ETM/e-ticket CSV.

    Timestamps are converted to naive IST wall-clock time (created_at behaves like boarding
    time, A-1). ``ticket_type_id`` is a single value for every row and is dropped.
    Exact duplicate rows are kept (identical tickets from different machines are plausible)
    and only counted.
    """
    raw = pd.read_csv(
        csv_path,
        usecols=["passenger_count", "amount", "vehicle_number", "end_stop_name", "route",
                 "start_stop_name", "created_at", "is_ac"],
        dtype={"route": "string", "start_stop_name": "string", "end_stop_name": "string",
               "vehicle_number": "string"},
        engine="pyarrow",
    )
    raw["vehicle_number"] = raw["vehicle_number"].mask(raw["vehicle_number"] == "NULL")
    rows_in = len(raw)
    ts = pd.to_datetime(raw["created_at"], format="ISO8601", utc=True, errors="coerce")
    ok_ts = ts.notna()
    pax = pd.to_numeric(raw["passenger_count"], errors="coerce")
    ok_pax = pax.fillna(0) >= 1
    keep = ok_ts & ok_pax
    dup = int(raw.duplicated().sum())

    raw = raw[keep].reset_index(drop=False)
    ts = ts[keep].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None).reset_index(drop=True)
    df = pd.DataFrame({
        "tid": raw["index"].astype("int64"),
        "ts": ts,
        "date": ts.dt.normalize(),
        "hour": ts.dt.hour.astype("int8"),
        "dow": ts.dt.dayofweek.astype("int8"),
        "minute_of_day": (ts.dt.hour * 60 + ts.dt.minute + ts.dt.second / 60).astype("float32"),
        "route": raw["route"].astype(object),
        "vehicle": raw["vehicle_number"].astype(object),
        "is_ac": raw["is_ac"].astype(bool),
        "pax": pax[keep].astype("int16").reset_index(drop=True),
        "amount": pd.to_numeric(raw["amount"], errors="coerce").astype("float32"),
        "start_name": raw["start_stop_name"].astype(object),
        "end_name": raw["end_stop_name"].astype(object),
    })
    df = df.sort_values("tid", kind="stable").reset_index(drop=True)[TICKET_COLUMNS]
    report = IngestReport(
        rows_in=rows_in,
        rows_out=len(df),
        dropped_bad_timestamp=int((~ok_ts).sum()),
        dropped_bad_pax=int((ok_ts & ~ok_pax).sum()),
        exact_duplicates_kept=dup,
        total_pax=int(df["pax"].sum()),
        null_vehicle_share=float(df["vehicle"].isna().mean()),
    )
    return df, report


def report_dict(report: IngestReport) -> dict:
    return asdict(report)
