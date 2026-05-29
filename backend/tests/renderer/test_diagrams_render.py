"""Test the Python script emitter — text-only, no graphviz required.

Full SVG/PNG rendering via the `diagrams` library needs graphviz on PATH and
is covered under tests/integration/test_diagrams_render_integration.py.
"""

from __future__ import annotations

import pytest

from app.renderer.diagrams_render import _emit_python_script, _py_escape, _py_handle
from app.renderer.models import Edge, Node, PopulatedPattern


def _pattern() -> PopulatedPattern:
    return PopulatedPattern(
        pattern_name="hub-spoke",
        title='Hub "Spoke" Topology',
        source_url="https://learn.microsoft.com/azure/architecture/hub-spoke",
        tiers=["edge", "hub", "spoke"],
        nodes=[
            Node(id="afd", label="Front Door", icon_id="front-door", tier="edge"),
            Node(id="vnet", label="Hub VNet", icon_id="virtual-network", tier="hub"),
            Node(id="app", label="App", icon_id="app-services", tier="spoke"),
        ],
        edges=[
            Edge(source="afd", target="app", label='HTTPS "TLS"'),
            Edge(source="vnet", target="app", style="dashed"),
        ],
    )


class TestEmitPythonScript:
    def test_script_is_syntactically_valid_python(self) -> None:
        src = _emit_python_script(_pattern(), basename="diagram")
        # Don't *execute* it (would import diagrams); just compile.
        compile(src, "<emitted>", "exec")

    def test_script_imports_diagrams(self) -> None:
        src = _emit_python_script(_pattern(), basename="d")
        assert "from diagrams import Cluster, Diagram, Edge" in src
        assert "from diagrams.custom import Custom" in src

    def test_script_resolves_icons_via_env_var_root(self) -> None:
        src = _emit_python_script(_pattern(), basename="d")
        assert 'ICONS_ROOT = Path(os.environ.get("ICONS_ROOT"' in src

    def test_script_does_not_inline_svg_bytes(self) -> None:
        """The standalone script must not bundle SVGs — it must reference the
        user's local V19 pack via manifest.json. This protects against icon
        redistribution outside an architecture diagram (spec §7)."""
        src = _emit_python_script(_pattern(), basename="d")
        assert "<?xml" not in src
        assert "base64" not in src

    def test_script_escapes_quotes_and_backslashes(self) -> None:
        src = _emit_python_script(_pattern(), basename="d")
        # The label 'Hub "Spoke" Topology' must be escaped (no raw `"` in the literal).
        assert 'Hub \\"Spoke\\" Topology' in src
        assert 'HTTPS \\"TLS\\"' in src

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ('say "hi"', r'say \"hi\"'),
            (r"back\slash", r"back\\slash"),
            ("clean", "clean"),
        ],
    )
    def test_py_escape(self, value: str, expected: str) -> None:
        assert _py_escape(value) == expected

    def test_py_handle_is_valid_identifier(self) -> None:
        assert _py_handle("afd_us_east_1").isidentifier()
        assert _py_handle("xyz") == "n_xyz"
