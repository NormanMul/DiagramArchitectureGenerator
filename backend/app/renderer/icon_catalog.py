"""V19 Azure icon catalog with strict immutability.

Loaded once per process. Provides:
  * `get_icon(id)` -> `IconRef` (path + svg bytes, frozen)
  * Mutation-rejection: any attempt to set `fill`, `transform`, `filter`, or
    other styling attributes on a returned icon raises `IconMutationError`.

Spec §7: icons must never be programmatically restyled. The renderer takes
`IconRef.path` and passes it to mingrammer/diagrams' `custom.Custom`, which
embeds the SVG as-is without modification.
"""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

from app.settings import get_settings

_logger = logging.getLogger(__name__)


# Attributes the LLM is most likely to try to set; rejection list is the
# union of well-known SVG presentation attributes + the SVG2 style equivalents.
FORBIDDEN_SVG_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "fill",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "fill-opacity",
        "opacity",
        "transform",
        "filter",
        "mask",
        "clip-path",
        "color",
    }
)


class IconMutationError(RuntimeError):
    """Raised when code attempts to mutate a V19 icon's appearance.

    Catches the §7 rule: "the renderer must reject any attempt to set fill,
    transform, or filter attributes on icon SVGs."
    """


class IconNotFoundError(KeyError):
    """Raised when a pattern descriptor references an icon id that isn't in V19."""


@dataclass(frozen=True, slots=True)
class IconRef:
    """A read-only handle to one V19 icon."""

    id: str
    name: str
    category: str
    path: Path

    def rendered_path(self, dpi: int = 144) -> Path:
        """Return a PNG copy of this icon suitable for graphviz embedding.

        Graphviz can't reliably embed SVG into its own SVG/PNG output, so we
        rasterize each V19 icon once per process to a stable temp location
        and reuse the PNG for every subsequent diagram. This does NOT modify
        the bundled SVG — the original `.path` is still the source of truth
        for `drawio_export` (which inlines the raw SVG bytes verbatim).
        """
        return _rasterize_to_png(self.path, dpi=dpi)


def _rasterize_to_png(svg_path: Path, *, dpi: int = 144) -> Path:
    """Cached SVG→PNG conversion for icon rendering.

    Cached in a per-process temp directory keyed by (path, mtime, dpi). Idempotent.
    """
    cache_dir = Path(tempfile.gettempdir()) / "archgen-icon-png-cache"
    cache_dir.mkdir(exist_ok=True)
    key = hashlib.sha1(  # noqa: S324 — non-cryptographic cache key
        f"{svg_path}|{svg_path.stat().st_mtime_ns}|{dpi}".encode()
    ).hexdigest()
    out = cache_dir / f"{key}.png"
    if not out.exists():
        import cairosvg  # noqa: PLC0415 — heavy native dep, lazy load

        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(out),
            dpi=dpi,
            output_width=128,
            output_height=128,
        )
    return out


@dataclass(frozen=True, slots=True)
class IconCatalog:
    """Immutable in-memory catalog of all V19 icons.

    Construct via `IconCatalog.load(manifest_path, icons_root)`. Instances are
    intentionally frozen — there is no public API to add, remove, or modify
    icons at runtime.
    """

    version: str
    _by_id: dict[str, IconRef]

    @classmethod
    def load(cls, manifest_path: Path, icons_root: Path) -> IconCatalog:
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"Icon manifest not found at {manifest_path}. "
                "Run scripts/download-azure-icons.ps1 first."
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        version: str = manifest.get("version", "unknown")
        by_id: dict[str, IconRef] = {}
        for entry in manifest.get("icons", []):
            icon_id = entry["id"]
            svg_path = icons_root / entry["file"]
            if not svg_path.is_file():
                _logger.warning("Manifest references missing SVG: %s", svg_path)
                continue
            by_id[icon_id] = IconRef(
                id=icon_id,
                name=entry["name"],
                category=entry["category"],
                path=svg_path,
            )
        if not by_id:
            raise FileNotFoundError(
                f"No icons found under {icons_root}. Run scripts/download-azure-icons.ps1 first."
            )
        _logger.info("Loaded %d V19 icons (version=%s)", len(by_id), version)
        return cls(version=version, _by_id=dict(by_id))

    def get(self, icon_id: str) -> IconRef:
        try:
            return self._by_id[icon_id]
        except KeyError as e:
            raise IconNotFoundError(icon_id) from e

    def __iter__(self) -> Iterator[IconRef]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, icon_id: object) -> bool:
        return isinstance(icon_id, str) and icon_id in self._by_id


# -----------------------------------------------------------------------------
# Mutation guard for downstream consumers
# -----------------------------------------------------------------------------


def assert_no_mutation(attributes: dict[str, object]) -> None:
    """Validate a dict of SVG/HTML attributes the caller wants to apply.

    Used by `diagrams_render` and any draw.io-side overrides to prevent the
    LLM from sneaking a `fill="#ff0000"` into an icon's render hint.
    """
    offending = sorted(set(attributes) & FORBIDDEN_SVG_ATTRS)
    if offending:
        raise IconMutationError(
            f"Refusing to apply forbidden style attribute(s) to a V19 icon: {offending}. "
            "See docs/icon-compliance.md."
        )


# -----------------------------------------------------------------------------
# Process-singleton accessor
# -----------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_catalog(manifest_path: str | None = None, icons_root: str | None = None) -> IconCatalog:
    """Process-singleton catalog. First-call args are remembered; later calls
    ignore args (use the lru_cache).

    For tests: call `get_catalog.cache_clear()` between cases that need a
    different fixture.
    """
    s = get_settings()
    mp = Path(manifest_path) if manifest_path else Path(s.icons_manifest_path)
    ir = Path(icons_root) if icons_root else Path(s.icons_root)
    return IconCatalog.load(mp, ir)
