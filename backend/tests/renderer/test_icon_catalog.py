"""Icon catalog + mutation rejection — spec §7."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.renderer.icon_catalog import (
    FORBIDDEN_SVG_ATTRS,
    IconCatalog,
    IconMutationError,
    IconNotFoundError,
    assert_no_mutation,
)


class TestCatalogLoad:
    def test_loads_expected_icons(self, catalog: IconCatalog) -> None:
        assert len(catalog) == 6
        assert "front-door" in catalog
        assert "cosmos-db" in catalog

    def test_version_pinned_to_V19(self, catalog: IconCatalog) -> None:
        assert catalog.version == "V19"

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            IconCatalog.load(tmp_path / "nope.json", tmp_path)

    def test_get_unknown_icon_raises(self, catalog: IconCatalog) -> None:
        with pytest.raises(IconNotFoundError):
            catalog.get("does-not-exist")

    def test_iteration_yields_all_icons(self, catalog: IconCatalog) -> None:
        ids = {icon.id for icon in catalog}
        assert ids == {
            "app-services",
            "container-apps",
            "front-door",
            "virtual-network",
            "cosmos-db",
            "azure-sql",
        }


class TestMutationRejection:
    """Spec §7: renderer rejects fill/transform/filter on icon SVGs."""

    @pytest.mark.parametrize("attr", sorted(FORBIDDEN_SVG_ATTRS))
    def test_each_forbidden_attribute_is_rejected(self, attr: str) -> None:
        with pytest.raises(IconMutationError) as exc_info:
            assert_no_mutation({attr: "anything"})
        assert attr in str(exc_info.value)

    def test_multiple_forbidden_attrs_listed_in_error(self) -> None:
        with pytest.raises(IconMutationError) as exc_info:
            assert_no_mutation({"fill": "#fff", "transform": "rotate(90)"})
        msg = str(exc_info.value)
        assert "fill" in msg
        assert "transform" in msg

    def test_safe_attrs_pass_through(self) -> None:
        # `label`, `x`, `y`, etc. are layout, not styling — allowed.
        assert_no_mutation({"label": "API", "x": "10", "y": "20"})

    def test_immutability_of_iconref(self, catalog: IconCatalog) -> None:
        icon = catalog.get("front-door")
        with pytest.raises((AttributeError, TypeError)):
            icon.id = "hacked"  # type: ignore[misc]
