"""Loader for the JSON pattern descriptors under app/patterns/.

Validates every descriptor against `PopulatedPattern` at import time so a
malformed pattern fails CI rather than at request time.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import lru_cache
from importlib import resources
from pathlib import Path

from app.renderer.models import PopulatedPattern


def _iter_descriptor_paths() -> Iterator[Path]:
    """Yield absolute paths to all JSON descriptors under app.patterns."""
    pkg_root = resources.files("app.patterns")
    for entry in pkg_root.iterdir():
        if entry.is_file() and entry.name.endswith(".json"):
            # importlib.resources returns a Traversable; cast to Path via str.
            yield Path(str(entry))


def _load_one(path: Path) -> PopulatedPattern:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PopulatedPattern.model_validate(raw)


@lru_cache(maxsize=1)
def load_all_patterns() -> dict[str, PopulatedPattern]:
    """Process-singleton registry: pattern_name -> PopulatedPattern."""
    registry: dict[str, PopulatedPattern] = {}
    for path in _iter_descriptor_paths():
        pattern = _load_one(path)
        if pattern.pattern_name in registry:
            raise ValueError(f"Duplicate pattern_name {pattern.pattern_name!r} in {path}")
        registry[pattern.pattern_name] = pattern
    return registry


def get_pattern(name: str) -> PopulatedPattern:
    """Look up a pattern by its `pattern_name`. Raises KeyError if missing."""
    return load_all_patterns()[name]
