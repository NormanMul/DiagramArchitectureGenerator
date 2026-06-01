"""Pydantic models for a populated pattern descriptor (the JSON that the
agent hands to the renderers).

A `PopulatedPattern` is the canonical input to BOTH `diagrams_render` and
`drawio_export`, guaranteeing the two outputs always describe the same graph.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Node(BaseModel):
    """One service in the diagram."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=80)
    icon_id: str = Field(min_length=1, description="V19 icon id from icons/manifest.json")
    tier: str = Field(min_length=1, max_length=40, description="Tier label for layout grouping")


class Edge(BaseModel):
    """Directed flow between two nodes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    target: str
    label: str = Field(default="", max_length=40)
    style: Literal["solid", "dashed", "dotted"] = "solid"


class PopulatedPattern(BaseModel):
    """A reference architecture pattern, populated with the user's services."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    source_url: str | None = Field(default=None, description="Microsoft Learn AAC URL")
    tiers: list[str] = Field(
        min_length=1, max_length=12, description="Ordered tier labels (top→bottom)"
    )
    nodes: list[Node] = Field(min_length=1, max_length=80)
    edges: list[Edge] = Field(default_factory=list, max_length=200)
    well_architected_notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _validate_consistency(self) -> PopulatedPattern:
        node_ids = {n.id for n in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("Duplicate node ids")
        tier_set = set(self.tiers)
        for n in self.nodes:
            if n.tier not in tier_set:
                raise ValueError(f"Node {n.id!r} tier {n.tier!r} not in declared tiers")
        for e in self.edges:
            if e.source not in node_ids:
                raise ValueError(f"Edge source {e.source!r} not in nodes")
            if e.target not in node_ids:
                raise ValueError(f"Edge target {e.target!r} not in nodes")
            if e.source == e.target:
                raise ValueError(f"Edge cannot self-loop: {e.source}")
        return self
