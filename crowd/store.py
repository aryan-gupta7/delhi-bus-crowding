"""Artefact store: parquet / npy / json files under ``out/`` with fixed schemas."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA_VERSION = "1"


def sha256_file(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


class Store:
    """Reads and writes the pipeline's artefacts; the only module that touches ``out/``."""

    def __init__(self, out_dir: Path):
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.out / name

    def exists(self, name: str) -> bool:
        return self.path(name).exists()

    def write_table(self, name: str, df: pd.DataFrame) -> None:
        table = pa.Table.from_pandas(df, preserve_index=False)
        table = table.replace_schema_metadata({"schema_version": SCHEMA_VERSION})
        pq.write_table(table, self.path(name), compression="zstd")

    def read_table(self, name: str, columns: list[str] | None = None) -> pd.DataFrame:
        return pq.read_table(self.path(name), columns=columns).to_pandas()

    def write_array(self, name: str, arr: np.ndarray) -> None:
        np.save(self.path(name), arr, allow_pickle=False)

    def read_array(self, name: str, mmap: bool = False) -> np.ndarray:
        return np.load(self.path(name), mmap_mode="r" if mmap else None, allow_pickle=False)

    def write_json(self, name: str, obj: Any) -> None:
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True, default=_json_default)

    def read_json(self, name: str) -> Any:
        with open(self.path(name), encoding="utf-8") as fh:
            return json.load(fh)

    def sha256(self, name: str) -> str:
        return sha256_file(self.path(name))


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    raise TypeError(f"not JSON serialisable: {type(obj)}")
