"""S0b on synthetic data: an outage hour, a stream-fault day, and untouched weekend peaks."""

import pandas as pd

from crowd.eligibility import build_day_hour_ok


def _tickets(days, volume):
    rows = []
    for day in days:
        for hour in range(24):
            n = volume(day, hour)
            rows += [(pd.Timestamp(day), hour, "V1", 1)] * (n // 2) + [(pd.Timestamp(day), hour, None, 1)] * (n // 2)
    return pd.DataFrame(rows, columns=["date", "hour", "vehicle", "pax"])


def test_outage_and_stream_fault_are_detected(real_config):
    days = pd.date_range("2026-10-05", periods=14, freq="D")          # Mon .. Sun, two weeks

    def volume(day, hour):
        base = 400 if 7 <= hour <= 10 else 150
        if day == pd.Timestamp("2026-10-07") and hour == 9:            # outage hour
            return 10
        return base

    t = _tickets(days, volume)
    # stream fault: on 2026-10-08 the tagged stream vanishes for the whole day
    t = t[~((t["date"] == "2026-10-08") & t["vehicle"].notna())]
    dh = build_day_hour_ok(t, real_config).set_index(["date", "hour"])
    assert dh.loc[(pd.Timestamp("2026-10-07"), 9), "reason"] == "outage"
    assert not dh.loc[(pd.Timestamp("2026-10-07"), 9), "hour_ok"]
    assert (dh.loc[pd.Timestamp("2026-10-08")]["reason"] == "stream_fault").all()
    assert dh.loc[(pd.Timestamp("2026-10-06"), 9), "hour_ok"]


def test_weekend_peaks_are_not_masked_by_weekday_medians(real_config):
    days = pd.date_range("2026-10-05", periods=14, freq="D")

    def volume(day, hour):
        weekend = day.dayofweek >= 5
        return (200 if weekend else 500) if 7 <= hour <= 10 else 100

    dh = build_day_hour_ok(_tickets(days, volume), real_config)
    weekend = dh[dh["date"].dt.dayofweek >= 5]
    assert (weekend["day_type"] == "weekend").all()
    assert weekend["hour_ok"].all()
