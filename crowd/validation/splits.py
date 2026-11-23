"""Day-blocked splits: tickets are never split, only whole days."""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd.config import Config


def weekday_split(day_hour_ok: pd.DataFrame, cfg: Config) -> tuple[np.ndarray, np.ndarray]:
    """Train = first ``validation.train_days`` eligible weekdays, test = all remaining ones."""
    ok = day_hour_ok[(day_hour_ok["day_type"] == "weekday") & day_hour_ok["hour_ok"]]
    days = np.sort(ok["date"].unique())
    n = cfg.validation.train_days
    return days[:n], days[n:]


def odd_even(days: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two disjoint halves of a set of days (for the noise ceiling)."""
    return days[::2], days[1::2]
