"""Export a `PopulatedPattern` to a draw.io (.drawio) XML file.

The .drawio format is a wrapped mxGraph XML; we emit the minimal subset that
the diagrams.net editor opens cleanly:

```
<mxfile host="genesis" agent="archgen-backend">
  <diagram name="..." id="...">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        ... vertex cells, group cells for tiers, edge cells ...
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

Icons are referenced via inline data URIs of the original V19 SVG bytes —
unmodified. We deliberately do NOT inline a transformed SVG.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from app.renderer.icon_catalog import IconCatalog, get_catalog
from app.renderer.models import PopulatedPattern

_logger = logging.getLogger(__name__)


# Visual layout constants (units are draw.io's "cells")
_TIER_WIDTH = 1000
_TIER_PADDING_X = 40
_TIER_PADDING_Y = 40
_TIER_HEADER_H = 30
_NODE_W = 120
_NODE_H = 120
_NODE_GAP = 30
_TIER_GAP_Y = 60


def export_drawio(
    pattern: PopulatedPattern,
    output_path: Path,
    *,
    catalog: IconCatalog | None = None,
) -> Path:
    """Write `pattern` as a .drawio XML file to `output_path`."""
    catalog = catalog or get_catalog()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mxfile = Element("mxfile", {"host": "genesis", "agent": "archgen-backend"})
    diagram = SubElement(
        mxfile,
        "diagram",
        {"name": pattern.title, "id": _slug(pattern.pattern_name)},
    )
    model = SubElement(diagram, "mxGraphModel", _model_attrs())
    root = SubElement(model, "root")
    SubElement(root, "mxCell", {"id": "0"})
    SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    next_id = 2
    tier_id_by_label: dict[str, str] = {}
    y_cursor = _TIER_PADDING_Y
    nodes_by_id: dict[str, str] = {}

    for tier in pattern.tiers:
        tier_nodes = [n for n in pattern.nodes if n.tier == tier]
        if not tier_nodes:
            continue
        tier_cell_id = str(next_id)
        next_id += 1
        tier_id_by_label[tier] = tier_cell_id
        cols = max(1, len(tier_nodes))
        tier_h = _TIER_HEADER_H + _TIER_PADDING_Y * 2 + _NODE_H
        tier_w = max(
            _TIER_WIDTH,
            _TIER_PADDING_X * 2 + cols * (_NODE_W + _NODE_GAP) - _NODE_GAP,
        )

        SubElement(
            root,
            "mxCell",
            {
                "id": tier_cell_id,
                "value": tier,
                "style": (
                    "rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;"
                    "fillColor=#F5F5F5;strokeColor=#9E9E9E;"
                    "fontStyle=1;fontSize=12;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        ).append(_geometry(_TIER_PADDING_X, y_cursor, tier_w, tier_h))

        node_x = _TIER_PADDING_X + _TIER_PADDING_X
        node_y = y_cursor + _TIER_HEADER_H + _TIER_PADDING_Y

        for node in tier_nodes:
            icon = catalog.get(node.icon_id)
            data_uri = _svg_to_data_uri(icon.path)
            node_cell_id = str(next_id)
            next_id += 1
            nodes_by_id[node.id] = node_cell_id

            SubElement(
                root,
                "mxCell",
                {
                    "id": node_cell_id,
                    "value": node.label,
                    "style": (
                        # `image=...` with a data URI — draw.io renders the SVG
                        # verbatim. No fill/transform applied by our XML.
                        "shape=image;verticalLabelPosition=bottom;"
                        "verticalAlign=top;imageAspect=1;"
                        f"image={data_uri};"
                        "labelBackgroundColor=#FFFFFF;fontSize=11;"
                    ),
                    "vertex": "1",
                    "parent": tier_cell_id,
                },
            ).append(_geometry(node_x - _TIER_PADDING_X, node_y - y_cursor, _NODE_W, _NODE_H))

            node_x += _NODE_W + _NODE_GAP

        y_cursor += tier_h + _TIER_GAP_Y

    for edge in pattern.edges:
        edge_cell_id = str(next_id)
        next_id += 1
        style = "endArrow=block;html=1;rounded=0;"
        if edge.style == "dashed":
            style += "dashed=1;"
        elif edge.style == "dotted":
            style += "dashPattern=1 4;dashed=1;"
        SubElement(
            root,
            "mxCell",
            {
                "id": edge_cell_id,
                "value": edge.label,
                "style": style,
                "edge": "1",
                "parent": "1",
                "source": nodes_by_id[edge.source],
                "target": nodes_by_id[edge.target],
            },
        ).append(_geometry(0, 0, 0, 0, relative=True))

    tree = ElementTree(mxfile)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    _logger.info("Exported drawio %s", output_path)
    return output_path


def _model_attrs() -> dict[str, str]:
    return {
        "dx": "0",
        "dy": "0",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "1",
        "pageScale": "1",
        "pageWidth": "1169",
        "pageHeight": "826",
        "math": "0",
        "shadow": "0",
    }


def _geometry(x: int, y: int, w: int, h: int, *, relative: bool = False) -> Element:
    attrs: dict[str, str] = {
        "x": str(x),
        "y": str(y),
        "width": str(w),
        "height": str(h),
        "as": "geometry",
    }
    if relative:
        attrs["relative"] = "1"
    return Element("mxGeometry", attrs)


def _svg_to_data_uri(svg_path: Path) -> str:
    """Embed an SVG as a base64 data URI — unmodified bytes."""
    raw = svg_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in value.lower()).strip("-")
