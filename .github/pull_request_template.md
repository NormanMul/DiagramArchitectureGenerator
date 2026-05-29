## Description

<!-- What does this PR do? Link the issue if any. -->

## Type of change

- [ ] feat
- [ ] fix
- [ ] refactor
- [ ] docs
- [ ] chore
- [ ] infra (Bicep)
- [ ] spec (changes to `docs/prompts.md`)

## Spec compliance checklist

- [ ] One concern per commit (Conventional Commits)
- [ ] No long-lived Azure secrets touched (OIDC only)
- [ ] No new icon assets added outside `icons/azure_V19/` (refresh workflow only)
- [ ] No SVG mutation paths added to the renderer
- [ ] If infra changed: `bicep what-if` output is attached / commented by CI
- [ ] If a new region/SKU is introduced: written justification in the PR body
- [ ] `ruff`, `mypy --strict`, `pytest` (≥80% coverage), `biome`, `tsc`, `vitest` all green locally
- [ ] If frontend UI changed: Microsoft icon attribution footer still present
