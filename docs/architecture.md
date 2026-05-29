# System Architecture

> Target architecture for **Genesis — Azure Architecture Diagram Generator**. The system itself runs on Azure (this document is dogfood).

## High-level

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  USER (browser)                                                             │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │ HTTPS (TLS 1.3, HSTS)
                ▼
       ┌────────────────────┐
       │ Azure Front Door   │  Standard tier + WAF policy
       │ Endpoint:          │  Custom rule: 60 req/min/IP on /api/generate
       │ diagramarchitec... │
       │ generator.azurefd  │
       │ .net               │
       └────────┬───────────┘
                │  Private Link to ACA env
        ┌───────┴────────┐
        ▼                ▼
┌──────────────────┐  ┌──────────────────────────────┐
│ ca-archgen-web   │  │ ca-archgen-api               │
│ (Next.js 15 SSR) │──▶ (FastAPI + diagrams +        │
│                  │  │  drawio export + MCP server) │
└──────────────────┘  └────────┬─────────────────────┘
                               │  Managed Identity
                               │  (no secrets in env vars)
            ┌──────────────────┼───────────────────────┐
            ▼                  ▼                       ▼
   ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐
   │ Foundry         │  │ Cosmos DB       │  │ Blob Storage     │
   │ fdy-archgen-    │  │ serverless      │  │ generated SVG/   │
   │ sea-01          │  │ conversation +  │  │ PNG/drawio,      │
   │ archgen-gpt54   │  │ user prefs      │  │ icon cache       │
   │ (GPT-5.4 v      │  └─────────────────┘  └──────────────────┘
   │  2026-03-05)    │           │                    │
   │ + AI Search     │           │                    │
   │ vector index    │           │                    │
   │ over patterns   │           │                    │
   └────────┬────────┘           │                    │
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │ Key Vault                │
                    │ (no app secrets — all    │
                    │  via managed identity)   │
                    └──────────────────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │ App Insights +           │
                    │ Log Analytics workspace  │
                    └──────────────────────────┘
```

## Networking

- VNet `vnet-archgen-prod-sea` (10.40.0.0/16) in Southeast Asia.
- Subnets:
  - `snet-aca` (10.40.0.0/23) — delegated to `Microsoft.App/environments`.
  - `snet-pe` (10.40.2.0/27) — private endpoints for Foundry, Cosmos, Storage, Key Vault, AI Search.
- Private DNS zones (linked to the VNet):
  - `privatelink.openai.azure.com`
  - `privatelink.documents.azure.com`
  - `privatelink.blob.core.windows.net`
  - `privatelink.vaultcore.azure.net`
  - `privatelink.search.windows.net`
- Container Apps environment is **internal-only**. Front Door reaches the apps via **Private Link** (origin type = `internalLoadBalancer`).
- NSG on `snet-aca` denies all public inbound; permits only AFD service tag for the Private Link plumbing.

## Identity & secrets

- **User-assigned managed identity** `id-archgen-prod-sea` is attached to both Container Apps and used for:
  - `AcrPull` on `crarchgenprodsea`
  - `Cosmos DB Built-in Data Contributor` on `cosmos-archgen-prod-sea`
  - `Storage Blob Data Contributor` on `starchgenprodsea`
  - `Key Vault Secrets User` on `kv-archgen-prod-sea`
  - `Cognitive Services OpenAI User` on `fdy-archgen-sea-01`
  - `Search Index Data Contributor` on `srch-archgen-prod-sea`
- The same MI is **federated** to the GitHub repo for OIDC (no `AZURE_CREDENTIALS` secret).
- All public network access on data plane resources is **disabled**. Reachable only via private endpoints.

## Cost (locked defaults)

| Service | SKU | Idle | Moderate |
|---|---|---|---|
| Front Door | Standard (WAF Standard rule set) | $35 | $45 |
| AI Search | Free tier (50 MB) | $0 | $0 |
| Foundry GPT-5.4 | Global Standard, TPM cap 50k, token budget 5k in / 2k out per session | $0 | ~$400 (500 gens/day) |
| Container Apps × 2 (api + web) | Consumption, scale-to-zero, min 0 max 3 | $0 | ~$30 |
| Cosmos DB | Serverless | $0 | ~$10 |
| Storage | LRS Standard | $1 | $3 |
| ACR | Basic | $5 | $5 |
| Log Analytics + App Insights | Pay-as-you-go, 25% success / 100% error sampling | $3 | $15 |
| Key Vault | Standard | <$1 | <$1 |
| **Total** | | **~$45** | **~$510** |

Budget alert configured at 50%, 80%, 100% of **USD $550/mo** on the resource group.

## Pattern-matching pipeline (no free-form layout)

1. User prompt is embedded and queried against the `archgen-patterns` AI Search vector index over `patterns_corpus/`.
2. Top 3 candidate patterns retrieved with their `tier_layout`, `services`, `flows`, and `well_architected_notes`.
3. GPT-5.4 picks **one** pattern with a written justification (token-counted against the session budget).
4. GPT-5.4 populates the chosen pattern's `tier_layout` with the user's specific service names + tier placements — it never lays out from scratch.
5. The populated structure is rendered:
   - To Python via `diagrams_render.py` (mingrammer/diagrams + V19 icons).
   - To `.drawio` XML via `drawio_export.py`.
   - To SVG/PNG via graphviz invoked by the diagrams library.

## Repository layout

```
.
├── README.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── CODEOWNERS
├── .editorconfig
├── .gitattributes
├── .gitignore
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── deploy-infra.yml
│   │   ├── deploy-app.yml
│   │   ├── deploy-frontend.yml
│   │   └── refresh-icons.yml
│   ├── dependabot.yml
│   └── CODEOWNERS
├── infra/
│   ├── main.bicep
│   ├── modules/
│   │   ├── foundry.bicep
│   │   ├── networking.bicep
│   │   ├── container-app.bicep
│   │   ├── front-door.bicep
│   │   ├── data.bicep
│   │   └── observability.bicep
│   └── parameters/
│       ├── dev.bicepparam
│       └── prod.bicepparam
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   ├── telemetry.py
│   │   ├── agents/
│   │   │   ├── architect.py
│   │   │   └── prompts/
│   │   ├── patterns/        (15 JSON descriptors)
│   │   ├── renderer/
│   │   │   ├── diagrams_render.py
│   │   │   ├── drawio_export.py
│   │   │   └── icon_catalog.py
│   │   └── mcp_server/
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── app/
│   ├── components/
│   └── public/
├── icons/
│   ├── azure_V19/           (downloaded, unmodified)
│   └── manifest.json
├── patterns_corpus/         (markdown, RAG source)
├── scripts/
│   ├── download-azure-icons.ps1
│   └── seed-patterns.py
└── docs/
    ├── architecture.md
    ├── operations.md
    ├── icon-compliance.md
    └── prompts.md
```
