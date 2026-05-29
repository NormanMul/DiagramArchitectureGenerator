"""Pytest fixtures for the backend test suite."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.renderer.icon_catalog import IconCatalog, get_catalog

# Minimal SVG body that's syntactically valid.
_MIN_SVG = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">\n'
    '  <rect x="2" y="2" width="20" height="20" fill="#0078D4"/>\n'
    "</svg>\n"
)


@pytest.fixture
def fake_icons_root(tmp_path: Path) -> Path:
    """Create a tiny icon set (3 categories x 2 icons) on disk."""
    root = tmp_path / "azure_V19"
    root.mkdir()
    fixtures: list[tuple[str, str, str]] = [
        ("compute", "00001-icon-service-app-services.svg", "app-services"),
        ("compute", "00002-icon-service-container-apps.svg", "container-apps"),
        ("networking", "10001-icon-service-front-door.svg", "front-door"),
        ("networking", "10002-icon-service-virtual-network.svg", "virtual-network"),
        ("databases", "20001-icon-service-cosmos-db.svg", "cosmos-db"),
        ("databases", "20002-icon-service-azure-sql.svg", "azure-sql"),
    ]
    icons = []
    for category, filename, icon_id in fixtures:
        cat_dir = root / category.capitalize()
        cat_dir.mkdir(exist_ok=True)
        (cat_dir / filename).write_text(_MIN_SVG, encoding="utf-8")
        icons.append(
            {
                "id": icon_id,
                "name": Path(filename).stem,
                "file": f"{category.capitalize()}/{filename}",
                "category": category,
            }
        )
    (root / "VERSION.txt").write_text("V19", encoding="utf-8")
    manifest = {
        "$comment": "fixture",
        "version": "V19",
        "generated_at": "2026-05-29T00:00:00Z",
        "icons": icons,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.fixture
def fake_manifest_path(fake_icons_root: Path) -> Path:
    return fake_icons_root.parent / "manifest.json"


@pytest.fixture
def catalog(fake_manifest_path: Path, fake_icons_root: Path) -> Iterator[IconCatalog]:
    cat = IconCatalog.load(fake_manifest_path, fake_icons_root)
    # Also wire into the lru_cache so code paths that call get_catalog() pick it up.
    get_catalog.cache_clear()
    yield cat
    get_catalog.cache_clear()
