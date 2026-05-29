"""Renderer subpackage.

Three responsibilities, each in its own module:

* `icon_catalog` — load and validate the V19 icon pack; reject any mutation.
* `diagrams_render` — turn a populated pattern descriptor into an SVG/PNG via
  the `diagrams` library (graphviz under the hood).
* `drawio_export` — emit equivalent draw.io XML for the same structure.
"""
