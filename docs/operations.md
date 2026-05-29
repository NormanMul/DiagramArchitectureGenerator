# Operations Runbook

> Steady-state operations for Genesis. Deploy procedures live in [.github/workflows/](../.github/workflows/) — this document covers monitoring, incident response, and routine maintenance.

## Service map

| Concern | Resource | Where to look |
|---|---|---|
| Public ingress | `afd-archgen-prod` | AFD metrics blade in Azure Portal |
| Frontend SSR | `ca-archgen-web-prod-sea` | App Insights → request telemetry |
| API / model calls | `ca-archgen-api-prod-sea` | App Insights → dependency telemetry |
| LLM | `fdy-archgen-sea-01` → `archgen-gpt54` | Foundry portal → metrics |
| RAG index | `srch-archgen-prod-sea` → `archgen-patterns` | AI Search Insights blade |
| Conversation store | `cosmos-archgen-prod-sea` | Cosmos metrics → RU consumption |
| Artifacts | `starchgenprodsea` → container `diagrams` | Storage metrics |
| Identity | `id-archgen-prod-sea` (user-assigned) | Entra → Managed Identities |
| Secrets store (unused at runtime) | `kv-archgen-prod-sea` | Key Vault access logs |

## Key dashboards

1. **App Insights → Application Map** — end-to-end traces (AFD → web → api → Foundry → renderer).
2. **App Insights → Failures** — group by exception type; the renderer raises `IconMutationError` if the LLM tries to recolor an icon.
3. **App Insights → Performance** — P50/P95/P99 on `/api/generate`. SLA target: **P95 ≤ 25 s** per §10.
4. **Cost Management → Resource Group `rg-archgen-prod-sea`** — daily cost vs budget alerts (50/80/100% of $550/mo).
5. **Foundry → archgen-gpt54** — TPM / RPM usage. Alert at 80% of 50k TPM cap.

## Token budget enforcement

- Server-side limit per session: **5 000 input tokens + 2 000 output tokens** (locked default; see [docs/prompts.md](prompts.md) §9).
- Enforced in [backend/app/agents/architect.py](../backend/app/agents/architect.py) using the model's token counter; over-budget requests return HTTP 429 with `Retry-After`.
- App Insights custom metric `archgen.session.tokens_used` records each session's actual usage.

## Routine maintenance

| Cadence | Task | Owner |
|---|---|---|
| Monthly | Icon refresh PR (`refresh-icons.yml` cron) | Architect on call |
| Monthly | Review App Insights failure trends | Architect on call |
| Monthly | Cost review vs budget | Architect on call |
| Quarterly | Pattern descriptor refresh (AAC catalog changes) | Architect on call |
| Quarterly | Bicep what-if against `prod.bicepparam` to catch drift | Architect on call |
| As needed | GPT-5.x model upgrade — pin in `infra/parameters/prod.bicepparam`, redeploy via `deploy-infra.yml` | Architect on call |

## Incident playbooks

### `/api/generate` returns 5xx

1. App Insights → Failures → group by `result code`.
2. If exception is `OpenAIRateLimitError`: check Foundry metrics; raise TPM cap or wait. Cap configured in `infra/parameters/prod.bicepparam`.
3. If exception is `IconMutationError`: this is a model regression — the agent tried to mutate a V19 icon. Capture the offending prompt + LLM output and file an issue. Roll back to the previous deployment via `az containerapp revision activate`.
4. If exception is `AISearchIndexNotFound`: the patterns index is missing. Re-run `scripts/seed-patterns.py` (or its CI equivalent in `deploy-app.yml`).

### Front Door endpoint down

1. Check AFD health probe metrics.
2. Failover: AFD has only one origin group (Container Apps env). If unhealthy:
   - `az containerapp revision list -g rg-archgen-prod-sea -n ca-archgen-api-prod-sea`
   - Activate the previous-known-good revision.
3. If the issue is the WAF policy itself (false positive blocking legit traffic): temporarily switch the AFD policy mode to `Detection` via Portal; investigate; switch back to `Prevention`.

### Cost spike

1. Cost Management → Cost Analysis filtered to the RG; group by `Service name`.
2. If Foundry is the spike: check Foundry → metrics for unusual TPM. Could be (a) an abusive client (look at AFD WAF logs for repeated source IPs — bump the rate-limit rule), or (b) a long-context session bypassing the token budget (audit `architect.py` enforcement path).
3. If AI Search is the spike: confirm we're still on Free tier (`srch-archgen-prod-sea` SKU). If accidentally upgraded, scale down.

## Disaster recovery

- **Cosmos**: serverless containers have automatic periodic backups (7-day window). For point-in-time restore, file a support ticket — manual via Portal.
- **Storage**: LRS only. Generated diagrams are ephemeral; loss is acceptable (users can regenerate). Pattern descriptors live in git and are reseedable.
- **AI Search Free tier**: no SLA. Index is rebuildable from `patterns_corpus/` via `scripts/seed-patterns.py`. RTO ≈ 5 min.
- **Foundry**: model deployment is recreated by `deploy-infra.yml`. Conversation history in Cosmos is preserved; in-flight requests fail.
- **Front Door custom hostname**: default `*.azurefd.net` requires no DNS state. If we add a custom domain later, document its registrar + TXT/CNAME records here.

## Decommission

```bash
az group delete -n rg-archgen-prod-sea --yes --no-wait
# AFD profile is at subscription scope, not in the RG:
az afd profile delete -g rg-archgen-prod-sea -n afd-archgen-prod --yes
# Confirm no remaining resources:
az resource list --query "[?starts_with(name,'archgen')]" -o table
```
