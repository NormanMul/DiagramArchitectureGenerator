# Build Spec — System Prompt (Frozen)

This is the system / initial-user prompt the project was built from. The agent
should treat sections 1–11 as the operating contract and 12–14 as appendices.

> _Frozen at 2026-05-29. Any future change must be a PR that updates this file
> AND the relevant code/docs in the same commit (Conventional Commits scope:
> `spec`)._

---

(See the original user prompt for §1 through §14; reproduced verbatim from the
project kickoff message.)

## §1. Role and operating mode
Senior Azure Cloud Solutions Architect + Full-Stack AI Engineer. Plan before
building. One concern per commit. Show evidence after each deploy step. Fail
loudly. Never invent — query the live environment or Microsoft Learn MCP.

## §2. Mission
Public AI-powered Azure architecture diagram generator. Pattern-matched
(never free-form). Outputs Python `diagrams` script + editable `.drawio` +
inline SVG. Chat-based iteration. Microsoft V19 icons unmodified.

## §3. Environment

- **Sub**: `ME-MngEnvMCAP818878-mprawironego-1` (Contoso MCAPS, NOT Microsoft corp).
- **Region**: `southeastasia` primary, `australiaeast` paired.
- **Foundry**: `fdy-archgen-sea-01`, model `gpt-5.4` v`2026-03-05`
  (Global Standard, confirmed available 2026-05-29).
- **GitHub**: repo `mprawironego_microsoft/Genesis-DiagramArchitectureGenerator`
  (adopted, not the prompt's proposed `azure-archgen`).
- **MCP servers wired into the agent**: GitHub MCP, Microsoft Learn MCP,
  custom diagrams-as-code MCP (we build).

## §4. Target architecture
See [architecture.md](architecture.md). **One deviation from the original
spec**: dropped Static Web Apps; Next.js SSR runs as a second Container App.
Front Door has a single origin group fronting both `ca-archgen-web` and
`ca-archgen-api`.

## §5. Repository layout
See [architecture.md#repository-layout](architecture.md#repository-layout).

## §6. Reference architecture pattern library
15 patterns seeded into `backend/app/patterns/` as JSON descriptors:

1. Basic web app (App Service + Azure SQL)
2. Hub-spoke network topology
3. Azure landing zone (CAF-aligned)
4. AKS baseline
5. Baseline OpenAI chat on Foundry
6. Web app with private endpoints + Front Door
7. Microsoft Fabric medallion analytics
8. SAP on Azure (HANA on Azure VMs)
9. Enterprise BI with Synapse
10. IoT reference architecture
11. Event-driven microservices on Container Apps
12. SQL Server to Azure SQL Managed Instance migration
13. Zero-trust network for web apps (App Gateway + Azure Firewall)
14. Multi-region active-active web app
15. AI agent orchestration with Foundry Agent Service

## §7. Icon compliance
See [icon-compliance.md](icon-compliance.md). Non-negotiable.

## §8. Security and identity
- Managed identity everywhere; zero secrets in code/env/pipeline.
- Foundry, Cosmos, Storage, KV, AI Search: private endpoints only, public
  network access disabled.
- Container App ingress: internal-only; Front Door reaches via Private Link.
- AFD WAF: Standard rule set + bot manager + custom rule
  (60 req/min/IP on `/api/generate`).
- App Insights sampling: 100% on errors, 25% on success.
- GH Actions: OIDC federation only.
- CodeQL + Dependabot + secret scanning enabled.

## §9. Cost guardrails (revised from original)
**Revised after live calc; see [architecture.md#cost-locked-defaults](architecture.md#cost-locked-defaults).**

| Metric | Original spec | Revised default | Why |
|---|---|---|---|
| Idle | < $80/mo | ~$45/mo | AFD Std + AI Search Free + ACA scale-to-zero |
| Moderate (500 gens/day) | < $250/mo | ~$510/mo | Realistic at GPT-5.4 prices with 5k/2k token cap. To get to $250 we'd cap at ~250 gens/day or use gpt-5.4-mini. |
| Token budget per session | 30k in + 8k out | 5k in + 2k out | Pattern-matching keeps prompts short; original budget was free-form-LLM-sized. |
| Budget alert threshold | $250/mo | $550/mo | Matches revised moderate-use estimate. |

## §10. Acceptance criteria
See spec body. Evidence captured per criterion in
[operations.md#key-dashboards](operations.md#key-dashboards).

## §11. First actions
Done 2026-05-29. See plan in `/memories/session/plan.md`.

## §12–14. Appendices
- A — references: Mingrammer compat-fork-diagrams on PyPI; Azure Icons V19;
  AAC catalog; Foundry endpoints; GitHub + Learn MCP; draw.io XML reference.
- B — coding standards: Python 3.12 + uv + ruff + mypy --strict + pytest ≥80%.
  TypeScript: Next.js 15 + strict + pnpm + biome + vitest + Playwright.
  Bicep: AVM where available, per-env params, lint clean. Conventional Commits.
- C — rejections: any icon recolor; any env-var secret; any free-form LLM
  layout; any deploy without `bicep what-if`; any non-SEA/AUS region without
  written justification (GPT-5.4 is in SEA → none needed); any long-lived SP
  secret; any README without a self-generated diagram.
