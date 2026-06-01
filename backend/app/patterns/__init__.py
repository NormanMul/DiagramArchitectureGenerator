"""Pattern descriptors.

Each JSON file in this package is a `PopulatedPattern` matching the schema in
`app.renderer.models.PopulatedPattern`. They are the seed corpus for the
RAG-based architect agent.

Source: Microsoft Azure Architecture Center (https://learn.microsoft.com/azure/architecture/browse/).
Each descriptor's `source_url` field links back to its canonical article.

Lifecycle:
  * On startup, the agent (architect.py) loads all *.json into memory.
  * `scripts/seed-patterns.py` populates an Azure AI Search index from these
    descriptors so the agent can do top-k vector retrieval over them.
  * The renderer (diagrams_render, drawio_export) consumes the same JSON
    shape, so the source of truth is single.
"""
