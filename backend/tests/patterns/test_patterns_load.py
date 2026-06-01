"""Validate that every JSON pattern descriptor loads cleanly + references well-formed icons."""

from __future__ import annotations

import pytest

from app.patterns.loader import load_all_patterns
from app.renderer.icon_catalog import IconCatalog

EXPECTED_PATTERN_NAMES = {
    "basic-web-app",
    "hub-spoke",
    "azure-landing-zone",
    "aks-baseline",
    "baseline-openai-chat",
    "web-app-private-endpoints",
    "fabric-medallion",
    "sap-on-azure",
    "enterprise-bi-synapse",
    "iot-reference",
    "event-driven-microservices",
    "sql-mi-migration",
    "zero-trust-web",
    "multi-region-active-active",
    "agent-orchestration-foundry",
}


class TestPatternsLoad:
    def test_all_patterns_parse(self) -> None:
        load_all_patterns.cache_clear()
        registry = load_all_patterns()
        assert len(registry) == 15
        assert set(registry.keys()) == EXPECTED_PATTERN_NAMES

    def test_every_pattern_has_source_url(self) -> None:
        for name, p in load_all_patterns().items():
            assert p.source_url is not None, f"{name} missing source_url"
            assert p.source_url.startswith("https://learn.microsoft.com/"), (
                f"{name} has non-Learn source_url"
            )

    def test_every_pattern_has_at_least_one_edge(self) -> None:
        for name, p in load_all_patterns().items():
            assert len(p.edges) >= 1, f"{name} has no edges"


class TestPatternIconIntegrity:
    @pytest.mark.parametrize("pattern_name", sorted(EXPECTED_PATTERN_NAMES))
    def test_pattern_icon_ids_are_well_formed(self, pattern_name: str) -> None:
        p = load_all_patterns()[pattern_name]
        for node in p.nodes:
            assert node.icon_id.replace("-", "").isalnum()
            assert node.icon_id == node.icon_id.lower()

    @pytest.mark.parametrize("pattern_name", sorted(EXPECTED_PATTERN_NAMES))
    def test_pattern_tier_layout_is_consistent(self, pattern_name: str) -> None:
        p = load_all_patterns()[pattern_name]
        used_tiers = {n.tier for n in p.nodes}
        declared_tiers = set(p.tiers)
        assert used_tiers <= declared_tiers

    def test_v19_icon_lookups_resolve(self, catalog: IconCatalog) -> None:
        """Patterns reference real V19 icon ids. In tests we only ship 6 fixture
        icons; when the catalog has the icon, it must resolve. Missing ones are
        validated separately by CI's icon-integrity job against the live pack.
        """
        for p in load_all_patterns().values():
            for node in p.nodes:
                if node.icon_id in catalog:
                    icon = catalog.get(node.icon_id)
                    assert icon.path.exists()
