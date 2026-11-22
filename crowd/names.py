"""Stop-name normalisation shared by ticket matching and the planner's stop search."""

from __future__ import annotations

import re
from functools import lru_cache

_NON_ALNUM = re.compile(r"[^0-9a-z/]+")


def make_normaliser(abbreviations: dict[str, str]):
    """Return a cached ``normalise(name)``: case-fold, strip punctuation, expand abbreviations.

    ``/`` is kept so composite names ("A / B") can be split later.
    """

    @lru_cache(maxsize=None)
    def normalise(name: str) -> str:
        text = _NON_ALNUM.sub(" ", str(name).casefold().replace("&", " and "))
        text = re.sub(r"\s*/\s*", " / ", text)
        tokens = [abbreviations.get(tok, tok) for tok in text.split()]
        return " ".join(tokens).strip(" /")

    return normalise


def split_composite(normalised: str) -> list[str]:
    """Parts of a composite name ``"a / b"`` (one element if not composite)."""
    return [p.strip() for p in normalised.split("/") if p.strip()]
