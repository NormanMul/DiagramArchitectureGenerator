"""Draw.io exporter — structure + icon-immutability checks.

We do NOT run the diagrams library here (it needs graphviz on PATH; covered
in a separate integration test marker). Draw.io export is pure XML and runs
in any environment.
"""

from __future__ import annotations

import base64
from pathlib import Path
from xml.etree import ElementTree as ET

from app.renderer.drawio_export import export_drawio
from app.renderer.icon_catalog import IconCatalog
from app.renderer.models import Edge, Node, PopulatedPattern


def _pattern() -> PopulatedPattern:
    return PopulatedPattern(
        pattern_name="hub-spoke",
        title="Hub-Spoke Landing Zone",
        tiers=["edge", "hub", "spoke"],
        nodes=[
            Node(id="afd", label="Front Door", icon_id="front-door", tier="edge"),
            Node(id="vnet", label="Hub VNet", icon_id="virtual-network", tier="hub"),
            Node(id="app", label="App", icon_id="app-services", tier="spoke"),
            Node(id="sql", label="SQL", icon_id="azure-sql", tier="spoke"),
        ],
        edges=[
            Edge(source="afd", target="app", label="HTTPS"),
            Edge(source="vnet", target="app", style="dashed"),
            Edge(source="app", target="sql", style="dotted"),
        ],
    )


class TestExportDrawio:
    def test_writes_well_formed_xml(self, tmp_path: Path, catalog: IconCatalog) -> None:
        out = export_drawio(_pattern(), tmp_path / "x.drawio", catalog=catalog)
        assert out.exists()
        tree = ET.parse(out)
        root = tree.getroot()
        assert root.tag == "mxfile"
        diagrams = root.findall("diagram")
        assert len(diagrams) == 1

    def test_emits_one_cell_per_node_plus_tiers_and_edges(
        self, tmp_path: Path, catalog: IconCatalog
    ) -> None:
        out = export_drawio(_pattern(), tmp_path / "x.drawio", catalog=catalog)
        tree = ET.parse(out)
        cells = tree.findall(".//mxCell")
        # 2 root cells (0 and 1) + 3 tier cells (all populated) + 4 nodes + 3 edges
        assert len(cells) == 2 + 3 + 4 + 3

    def test_icons_embedded_as_unmodified_base64(
        self, tmp_path: Path, catalog: IconCatalog
    ) -> None:
        out = export_drawio(_pattern(), tmp_path / "x.drawio", catalog=catalog)
        xml = out.read_text(encoding="utf-8")
        # Pull out one icon's source bytes and confirm its b64 appears verbatim
        # in the XML — i.e., we did not transform it.
        icon = catalog.get("front-door")
        raw = icon.path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        assert b64 in xml, "draw.io export must embed the V19 SVG byte-for-byte"

    def test_empty_tiers_omitted(self, tmp_path: Path, catalog: IconCatalog) -> None:
        # Three declared tiers but only two populated -> no empty tier cells.
        p = PopulatedPattern(
            pattern_name="x",
            title="X",
            tiers=["edge", "middle", "data"],
            nodes=[
                Node(id="a", label="A", icon_id="front-door", tier="edge"),
                Node(id="b", label="B", icon_id="cosmos-db", tier="data"),
            ],
        )
        out = export_drawio(p, tmp_path / "x.drawio", catalog=catalog)
        tree = ET.parse(out)
        tier_values = {
            c.get("value")
            for c in tree.findall(".//mxCell")
            if c.get("vertex") == "1" and c.get("value") in {"edge", "middle", "data"}
        }
        assert tier_values == {"edge", "data"}

    def test_edge_styles_serialize(self, tmp_path: Path, catalog: IconCatalog) -> None:
        out = export_drawio(_pattern(), tmp_path / "x.drawio", catalog=catalog)
        xml = out.read_text(encoding="utf-8")
        assert "dashed=1" in xml
        assert "dashPattern=1 4" in xml
