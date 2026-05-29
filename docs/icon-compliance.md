# Icon Compliance

> Compliance evidence for §7 of the build spec: Microsoft Azure Architecture Icons (V19) bundled unmodified, with Terms of Use surfaced.

## What we ship

| Item | Location |
|---|---|
| Icon set (V19, SVG) | [`icons/azure_V19/`](../icons/azure_V19/) |
| Microsoft Terms of Use | [`icons/azure_V19/Terms_of_Use.pdf`](../icons/azure_V19/Terms_of_Use.pdf) |
| Icon manifest (name → file → category) | [`icons/manifest.json`](../icons/manifest.json) |
| Downloader script (idempotent) | [`scripts/download-azure-icons.ps1`](../scripts/download-azure-icons.ps1) |
| Monthly refresh workflow | [`.github/workflows/refresh-icons.yml`](../.github/workflows/refresh-icons.yml) |
| Renderer with mutation rejection | [`backend/app/renderer/icon_catalog.py`](../backend/app/renderer/icon_catalog.py) |
| UI footer attribution | [`frontend/app/components/Footer.tsx`](../frontend/app/components/Footer.tsx) |

## Compliance matrix

| Rule (from spec §7) | How enforced |
|---|---|
| Icons live in `icons/azure_V19/` exactly as downloaded from Microsoft Learn. | Downloader script writes them byte-for-byte from the official zip; `.gitattributes` declares `*.svg binary` to prevent EOL normalization. |
| Never recolor, rotate, flip, crop, or restyle programmatically. | `icon_catalog.py` parses each SVG once and rejects any subsequent attempt to set `fill`, `transform`, or `filter` attributes. Raises `IconMutationError`. Unit tests in `backend/tests/renderer/test_icon_catalog.py` exercise the rejection path. |
| Microsoft Terms of Use bundled. | `Terms_of_Use.pdf` lives next to the icon set and is downloaded by the same script. |
| Terms surfaced in UI. | Footer component renders: _"Azure service icons © Microsoft, used under the [Terms of Use](https://learn.microsoft.com/azure/architecture/icons/#legal)."_ |
| Users cannot export an individual icon. | The API exposes `/api/generate` → diagram bundle (SVG + PNG + .drawio + .py) but no endpoint that returns a single icon. The frontend `/api/icon/[name]` route returns 404. |
| Monthly refresh check. | `refresh-icons.yml` runs on the first of each month: downloads the latest V-N pack, diffs against the bundled version, opens a PR if changed. The PR is reviewed before merge to ensure no surprise breaking changes to icon filenames. |

## Verifying compliance locally

```bash
# 1. Re-download to a temp location and diff against the bundled set.
pwsh ./scripts/download-azure-icons.ps1 -OutputDir /tmp/azure_V19_check
diff -r icons/azure_V19/ /tmp/azure_V19_check/
# Expect: no differences.

# 2. Run the renderer's compliance unit tests.
cd backend
uv run pytest tests/renderer/test_icon_catalog.py -v
# Expect: all tests pass, including the four mutation-rejection cases.

# 3. Smoke-test the UI footer.
cd ../frontend
pnpm dev
# Open http://localhost:3000 → footer shows the attribution + link.
```

## If a new V-N pack adds breaking changes

When `refresh-icons.yml` opens a PR with renamed or removed SVG files:

1. Diff `icons/manifest.json` — the script regenerates it; review for renames.
2. Search `backend/app/patterns/*.json` for any `icon_name` field that points at a now-missing file. The CI step `pytest backend/tests/patterns/test_pattern_icons_exist.py` catches this.
3. Update the affected pattern descriptors. Do **not** keep the old icon by copying it from the previous pack — that would be a modification of the V-N pack.

## What we do **not** do

- We do not vendor or rehost the icon SVGs outside this repo (e.g., on a CDN we control). Users get them inline inside generated diagrams only.
- We do not embed the icons in any branded image (badges, social previews, slide templates) outside actual diagrams.
- We do not strip the Microsoft copyright comment from any SVG.
