"""Pydantic model validation for `PopulatedPattern`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.renderer.models import Edge, Node, PopulatedPattern


def _valid_pattern() -> PopulatedPattern:
    return PopulatedPattern(
        pattern_name="hub-spoke",
        title="Hub-Spoke Landing Zone",
        source_url="https://learn.microsoft.com/azure/architecture/hub-spoke",
        tiers=["edge", "hub", "spoke"],
        nodes=[
            Node(id="afd", label="Front Door", icon_id="front-door", tier="edge"),
            Node(id="vnet", label="Hub VNet", icon_id="virtual-network", tier="hub"),
            Node(id="app", label="App Services", icon_id="app-services", tier="spoke"),
        ],
        edges=[
            Edge(source="afd", target="app", label="HTTPS"),
            Edge(source="vnet", target="app", style="dashed"),
        ],
    )


class TestPopulatedPattern:
    def test_valid_pattern_constructs(self) -> None:
        p = _valid_pattern()
        assert p.title == "Hub-Spoke Landing Zone"
        assert len(p.nodes) == 3

    def test_duplicate_node_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate node ids"):
            PopulatedPattern(
                pattern_name="x",
                title="X",
                tiers=["t"],
                nodes=[
                    Node(id="a", label="A", icon_id="front-door", tier="t"),
                    Node(id="a", label="A2", icon_id="front-door", tier="t"),
                ],
            )

    def test_node_with_unknown_tier_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not in declared tiers"):
            PopulatedPattern(
                pattern_name="x",
                title="X",
                tiers=["edge"],
                nodes=[
                    Node(id="a", label="A", icon_id="front-door", tier="ghost-tier"),
                ],
            )

    def test_edge_with_unknown_endpoint_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not in nodes"):
            PopulatedPattern(
                pattern_name="x",
                title="X",
                tiers=["t"],
                nodes=[Node(id="a", label="A", icon_id="front-door", tier="t")],
                edges=[Edge(source="a", target="nobody")],
            )

    def test_self_loop_rejected(self) -> None:
        with pytest.raises(ValidationError, match="self-loop"):
            PopulatedPattern(
                pattern_name="x",
                title="X",
                tiers=["t"],
                nodes=[Node(id="a", label="A", icon_id="front-door", tier="t")],
                edges=[Edge(source="a", target="a")],
            )

    def test_node_id_charset_enforced(self) -> None:
        with pytest.raises(ValidationError):
            Node(id="bad id with spaces", label="A", icon_id="front-door", tier="t")

    def test_node_id_allows_kebab_and_snake(self) -> None:
        # Both styles are valid — pattern descriptors use kebab-case.
        Node(id="agent-1", label="A", icon_id="front-door", tier="t")
        Node(id="agent_1", label="A", icon_id="front-door", tier="t")

    def test_too_many_nodes_rejected(self) -> None:
        nodes = [Node(id=f"n{i}", label=f"N{i}", icon_id="front-door", tier="t") for i in range(81)]
        with pytest.raises(ValidationError):
            PopulatedPattern(pattern_name="x", title="X", tiers=["t"], nodes=nodes)
