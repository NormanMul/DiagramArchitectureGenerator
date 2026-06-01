"""Render a `PopulatedPattern` to SVG/PNG using the `diagrams` library.

The `diagrams` library generates a graphviz DOT file under the hood; we use
`custom.Custom` to point at our V19 SVG icons (unmodified). Tiers map to
`Cluster` groupings to enforce the layout the pattern dictates.

Output goes to a caller-supplied directory; the caller (the FastAPI route)
uploads to Blob Storage and returns signed URLs.
"""

from __future__ import annotations

import base64
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from diagrams import Cluster, Diagram
from diagrams import Edge as DiagEdge
from diagrams.custom import Custom

from app.renderer.icon_catalog import IconCatalog, IconNotFoundError, get_catalog
from app.renderer.models import PopulatedPattern

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RenderResult:
    svg_path: Path
    png_path: Path
    py_script_path: Path


def render_pattern(
    pattern: PopulatedPattern,
    output_dir: Path,
    *,
    catalog: IconCatalog | None = None,
    basename: str = "diagram",
) -> RenderResult:  # pragma: no cover - needs graphviz on PATH (CI integration)
    """Render `pattern` to SVG + PNG + a re-runnable Python script.

    Raises:
        IconNotFoundError: if any node references an icon id missing from V19.
        ValueError: if graphviz is missing on PATH (diagrams library raises
            this internally).
    """
    catalog = catalog or get_catalog()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-flight: every icon must exist. Fail loudly *before* we invoke graphviz.
    for node in pattern.nodes:
        if node.icon_id not in catalog:
            raise IconNotFoundError(node.icon_id)

    svg_path = output_dir / f"{basename}.svg"
    png_path = output_dir / f"{basename}.png"

    # Render SVG via graphviz (which can reference PNG icons via xlink:href).
    with Diagram(
        name=pattern.title,
        filename=str(output_dir / basename),
        outformat="svg",
        show=False,
        direction="TB",
        graph_attr={
            "bgcolor": "white",
            "pad": "0.5",
            "fontname": "DejaVu Sans",
        },
        node_attr={"fontname": "DejaVu Sans", "fontsize": "11"},
        edge_attr={"fontname": "DejaVu Sans", "fontsize": "9"},
    ):
        node_handles: dict[str, Custom] = {}
        for tier in pattern.tiers:
            tier_nodes = [n for n in pattern.nodes if n.tier == tier]
            if not tier_nodes:
                continue
            with Cluster(tier):
                for node in tier_nodes:
                    icon = catalog.get(node.icon_id)
                    # Use a rasterized PNG copy — graphviz embeds raster
                    # bitmaps reliably but cannot embed SVG. The original
                    # bundled SVG is still untouched (drawio_export uses it
                    # verbatim).
                    png_icon = icon.rendered_path()
                    node_handles[node.id] = Custom(node.label, str(png_icon))

        for edge in pattern.edges:
            src = node_handles[edge.source]
            dst = node_handles[edge.target]
            attrs: dict[str, str] = {}
            if edge.style != "solid":
                attrs["style"] = edge.style
            if edge.label:
                attrs["label"] = edge.label
            src >> DiagEdge(**attrs) >> dst

    # The diagrams library writes filename.svg; ensure our basename is honored.
    produced_svg = output_dir / f"{basename}.svg"
    if produced_svg != svg_path:
        shutil.move(str(produced_svg), str(svg_path))

    # Inline the icon PNGs into the SVG so the file is self-contained
    # (otherwise xlink:href points to a temp path that won't resolve in a
    # browser or when downloaded).
    _inline_image_refs(svg_path)

    # Generate PNG from the inlined SVG so both formats are pixel-equivalent.
    _svg_to_png(svg_path, png_path)

    py_script = _emit_python_script(pattern, basename=basename)
    py_path = output_dir / f"{basename}.py"
    py_path.write_text(py_script, encoding="utf-8")

    _logger.info("Rendered pattern %s → %s + .png + .py", pattern.pattern_name, svg_path.name)
    return RenderResult(svg_path=svg_path, png_path=png_path, py_script_path=py_path)


def _inline_image_refs(svg_path: Path) -> None:
    """Rewrite any local-path xlink:href to a base64 data URI.

    Graphviz emits `xlink:href="/abs/path.png"` for `Custom` nodes; that won't
    resolve in a browser. We base64-inline the PNG so the SVG is portable.
    """
    svg = svg_path.read_text(encoding="utf-8")
    pattern_re = re.compile(r'xlink:href="([^"]+\.png)"')

    def _replace(match: re.Match[str]) -> str:
        ref = match.group(1)
        if ref.startswith("data:"):
            return match.group(0)
        p = Path(ref)
        if not p.is_file():
            return match.group(0)
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f'xlink:href="data:image/png;base64,{b64}"'

    rewritten = pattern_re.sub(_replace, svg)
    svg_path.write_text(rewritten, encoding="utf-8")


def _svg_to_png(svg_path: Path, png_path: Path) -> None:
    """Rasterize the final SVG to PNG via cairosvg."""
    import cairosvg  # noqa: PLC0415 — heavy native dep, lazy load

    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=1600,
    )


def _emit_python_script(pattern: PopulatedPattern, *, basename: str) -> str:
    """Emit a stand-alone Python script that the user can re-run locally.

    The script imports `diagrams` and resolves icon paths via an env var so it
    works against the user's local V19 download (it must NOT bundle SVGs).
    """
    lines: list[str] = [
        '"""Auto-generated by Genesis (https://diagramarchitecturegenerator.azurefd.net/).',
        f"Pattern: {pattern.pattern_name}",
        f"Source:  {pattern.source_url or 'N/A'}",
        "",
        "Prereqs: Microsoft Azure Architecture Icons V19 unpacked at $ICONS_ROOT.",
        '"""',
        "from __future__ import annotations",
        "",
        "import json",
        "import os",
        "from pathlib import Path",
        "",
        "from diagrams import Cluster, Diagram, Edge",
        "from diagrams.custom import Custom",
        "",
        'ICONS_ROOT = Path(os.environ.get("ICONS_ROOT", "./icons/azure_V19")).resolve()',
        "",
        "",
        "def _resolve_icon(icon_id: str) -> str:",
        '    """Resolve a V19 icon id to a relative path via manifest.json."""',
        '    manifest = json.loads((ICONS_ROOT / ".." / "manifest.json").read_text())',
        '    for icon in manifest["icons"]:',
        '        if icon["id"] == icon_id:',
        '            return icon["file"]',
        '    raise KeyError(f"Icon not found in V19 manifest: {icon_id}")',
        "",
        "",
        f'with Diagram(name="{_py_escape(pattern.title)}", filename="{basename}",'
        f' outformat="svg", show=False, direction="TB"):',
    ]
    indent = "    "
    handle_for: dict[str, str] = {}
    for tier in pattern.tiers:
        tier_nodes = [n for n in pattern.nodes if n.tier == tier]
        if not tier_nodes:
            continue
        lines.append(f'{indent}with Cluster("{_py_escape(tier)}"):')
        for n in tier_nodes:
            handle = _py_handle(n.id)
            handle_for[n.id] = handle
            lines.append(
                f'{indent * 2}{handle} = Custom("{_py_escape(n.label)}", '
                f'str(ICONS_ROOT / _resolve_icon("{n.icon_id}")))'
            )
    for e in pattern.edges:
        src = handle_for[e.source]
        dst = handle_for[e.target]
        edge_args = []
        if e.style != "solid":
            edge_args.append(f'style="{e.style}"')
        if e.label:
            edge_args.append(f'label="{_py_escape(e.label)}"')
        if edge_args:
            lines.append(f"{indent}{src} >> Edge({', '.join(edge_args)}) >> {dst}")
        else:
            lines.append(f"{indent}{src} >> {dst}")
    return "\n".join(lines) + "\n"


def _py_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _py_handle(node_id: str) -> str:
    """Convert a kebab-case node id to a safe Python identifier."""
    return "n_" + node_id.replace("-", "_")
