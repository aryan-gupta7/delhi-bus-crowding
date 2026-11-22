"""Typed, hashable access to config.yaml (the single source of every parameter)."""

from __future__ import annotations

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
        """Stable SHA-256 of the whole config or of the named top-level sections."""
        data = {k: self._data[k] for k in sections} if sections else self._data
        blob = json.dumps(data, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    def path(self, key: str) -> Path:
        """Resolve ``paths.<key>`` relative to the directory holding config.yaml."""
        return (self.root / self._data["paths"][key]).resolve()
