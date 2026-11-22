"""Typed, hashable access to config.yaml (the single source of every parameter)."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class Config:
    """Read-only nested mapping with attribute access: ``cfg.eligibility.mask_ratio``."""

    def __init__(self, data: dict[str, Any], root: Path):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "root", root)

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "Config":
        path = Path(path).resolve()
        with open(path, encoding="utf-8") as fh:
            return cls(yaml.safe_load(fh), path.parent)

    def __getattr__(self, name: str) -> Any:
        try:
            value = self._data[name]
        except KeyError:
            raise AttributeError(f"config has no key '{name}'") from None
        return Config(value, self.root) if isinstance(value, dict) else value

    def __getitem__(self, name: str) -> Any:
        return getattr(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Config is read-only")

    def to_dict(self) -> dict[str, Any]:
        return self._data

    def hash(self, *sections: str) -> str:
        """Stable SHA-256 of the named top-level sections, or of everything except ``paths``
        (where files live must not change the identity of a run)."""
        data = {k: self._data[k] for k in sections} if sections else {k: v for k, v in self._data.items() if k != "paths"}
        blob = json.dumps(data, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    def with_overrides(self, overrides: dict[str, Any]) -> "Config":
        """A copy with dotted keys replaced, e.g. ``{"ensemble.sigma_r": 0.9}`` (used by V3 and V9)."""
        data = copy.deepcopy(self._data)
        for dotted, value in overrides.items():
            *parents, leaf = dotted.split(".")
            node = data
            for key in parents:
                node = node[key]
            node[leaf] = value
        return Config(data, self.root)

    def path(self, key: str) -> Path:
        """Resolve ``paths.<key>`` relative to the directory holding config.yaml."""
        return (self.root / self._data["paths"][key]).resolve()
