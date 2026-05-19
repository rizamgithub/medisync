# MediSync — Agent Context (Azure Edition)

> **Read this first.** This file is the single source of truth for any AI agent (Claude Code, Cursor, Copilot, future me) working on this repo. If something here conflicts with the legacy `.md` specs, **this file wins** unless the user says otherwise.
>
> **History:** This project was originally designed against AWS (see `docs/_archive/context-aws.md`). It pivoted to **Azure** on **2026-05-19** after an AWS account suspension. The architectural patterns (event-driven, Saga, RBAC, geo-matching, IaC, distributed tracing) are unchanged — only the cloud vendor and service mapping changed.

---

## 1. What this project is

**MediSync** — an event-driven emergency blood/organ supply-chain platform. A portfolio project for the user (a software engineer building Azure credentials for job applications).

**Primary goal:** Get the user interviews. Optimize for:
- Azure keyword density (Functions, Cosmos DB, Entra ID, Event Grid, Durable Functions, Managed Identities, RBAC, Application Insights, Bicep/Terraform).
- Clean architecture patterns recruiters recognize (event-driven, Saga, RBAC, IaC, distributed tracing).
- A live demo that costs **$0–$2/month** to keep online.

**Secondary goal:** Be a real, working system the user can extend.

---

## 2. Non-Negotiable Rules

1. **No expensive Azure services in Phase 1.** Banned: AKS, App Service Plans (P1+), VMs, VNet/NAT Gateway, Application Gateway, Front Door Premium, Azure SQL, Synapse, Event Hubs Dedicated, Service Bus Premium. If you think you need one, stop and ask.
2. **Everything scales to zero.** Azure Functions consumption plan + Cosmos DB serverless + Event Grid. No always-on compute.
3. **100% Terraform.** Never create Azure resources via portal clicks (runbooks are the exception — they document one-time account/identity bootstrap). If a resource exists in Azure that isn't in `infra/*.tf`, treat it as a bug.
4. **No long-lived Azure secrets in CI.** GitHub Actions authenticates via OIDC federated credentials on the `medisync-deploy` service principal. No client secrets in repo secrets.
5. **No hardcoded secrets.** Use **Key Vault** with **Function App "Key Vault references"** (`@Microsoft.KeyVault(SecretUri=...)`). Free tier: 10k transactions/month free per vault.
6. **Least-privilege RBAC.** Every Function App identity gets a Managed Identity with role assignments scoped to specific resources (not the resource group, never the subscription). No `Contributor` for runtime identities — use data-plane roles (`Storage Blob Data Contributor`, `Cosmos DB Built-in Data Contributor`, etc.).
7. **`terraform destroy` must always work.** If you add a resource that blocks destroy (Storage with blobs + immutability, Cosmos accounts with soft-delete retention, Key Vaults with purge protection), add the cleanup to the destroy path or disable the blocker for non-prod.
8. **Cost guardrails come first.** Account-level: $5 monthly budget with 50/80/100% alerts (done — runbook 01). Subscription-level: Free Trial spending limit stays ON until we deliberately upgrade to PAYG.

---

## 3. Stack

### Backend (per service)
- **Language:** Python 3.12
- **Runtime:** **Azure Functions, Python v2 programming model**, consumption plan, Linux.
- **HTTP layer:** Functions HTTP triggers. (FastAPI is optional via `azurefunctions-extensions-http-fastapi` if a service grows enough endpoints to warrant it; default is plain Function decorators.)
- **Package manager:** `uv`
- **Validation/schemas:** Pydantic v2
- **Azure SDK:** `azure-functions`, `azure-cosmos`, `azure-identity`, `azure-eventgrid`, `azure-storage-blob`, `azure-keyvault-secrets`
- **Auth in code:** `DefaultAzureCredential` from `azure-identity` (uses Managed Identity in cloud, az login locally)
- **Tracing:** **OpenTelemetry** + **Azure Monitor exporter** (`azure-monitor-opentelemetry`) → Application Insights
- **Testing:** `pytest`, `pytest-asyncio`, in-process Function host via `func start`, `azure-cosmos` emulator for integration tests

### Frontend
- **Framework:** Next.js 14+ (App Router), TypeScript
- **Hosting:** **Azure Static Web Apps** (Free tier — 100 GB bandwidth/month)
- **Auth client:** **MSAL.js** with **Entra External ID**
- **Package manager:** `pnpm`

### Infrastructure
- **IaC:** Terraform (`azurerm` provider v4.x)
- **State:** Azure Storage Account + container, locked via state container's built-in lease (no separate DynamoDB-style lock table needed)
- **CI/CD:** GitHub Actions + OIDC federated credential → `medisync-deploy` SP

### Local dev
- **Cosmos DB Emulator** (docker) — `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator`
- **Azurite** (docker) for Blob/Queue/Table Storage emulation
- **`docker-compose.yml`** runs Cosmos emulator + Azurite + all Function services via `func start`
- **`func start --port <N>`** runs each Function app locally (one process per service)

---

## 4. Azure Service Map

| Concern | Service | Free-tier note |
|---|---|---|
| Auth | **Entra External ID** | 50k MAU free per tenant |
| All databases | **Cosmos DB for NoSQL (serverless)** | 1000 RU/s and 25 GB free always |
| Compute | **Azure Functions (Python 3.12, consumption Linux)** | 1M executions + 400k GB-s free always |
| HTTP edge | Functions HTTP triggers (API Management deferred) | included with Functions |
| Events | **Event Grid (system topics + custom topics)** | 100k operations/month free |
| Saga | **Durable Functions** (orchestrator + activities) | billed as regular Function executions |
| Email | **Azure Communication Services — Email** | 100 emails/month free; pay-per after |
| Logs | **Azure Monitor Logs (Log Analytics)** | 5 GB free per workspace per month |
| Tracing | **Application Insights** (workspace-based) | first 5 GB/month free |
| Secrets/config | **Key Vault** + **Function App Key Vault references** | 10k transactions/month free per vault |
| Frontend host | **Static Web Apps (Free tier)** | 100 GB bandwidth/month free |
| Object storage | **Blob Storage (Cool tier for archive, Hot for active)** | 5 GB free first 12 months only |
| Cost monitoring | **Cost Management Budgets + Action Groups** | free |
| Identity for workloads | **Managed Identities (system-assigned)** | free |

---

## 5. Repo Layout (target)

```
.
├── README.md                       ← public face: architecture, Saga story, live demo link
├── context.md                      ← THIS FILE
├── spec.md                         ← original spec (kept for history; Azure amendments applied)
├── Requirement.md                  ← original requirements (kept for history)
├── use_case.md                     ← "Golden Hour" narrative — interview-prep gold
├── docker-compose.yml              ← local dev: Cosmos emulator + Azurite
├── docs/
│   ├── runbooks/                   ← versioned ops procedures (01 account, 02 RBAC, 03 tooling)
│   └── _archive/                   ← superseded design docs (AWS-era context, archived runbooks)
├── .claude/
│   └── settings.json               ← MCP server config
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── infra/                          ← Terraform
│   ├── main.tf
│   ├── backend.tf                  ← azurerm backend on Storage Account container
│   ├── identity.tf                 ← User-Assigned MIs, role assignments
│   ├── cosmos.tf
│   ├── functions.tf                ← Function apps + Storage accounts they need
│   ├── eventgrid.tf
│   ├── durable.tf                  ← Durable Functions hub Storage Account
│   ├── communication.tf            ← ACS Email
│   ├── observability.tf            ← App Insights, Log Analytics, budgets
│   ├── keyvault.tf
│   └── probe/                      ← throw-away config used in runbook 03 to verify auth
├── services/
│   ├── user/                       ← Function app; Entra External ID + profile Cosmos container
│   ├── inventory/                  ← Function app; inventory Cosmos container + geo query
│   └── match/                      ← Function app; emits Event Grid events + Durable orchestrator
├── packages/
│   └── shared/                     ← Pydantic event schemas (typed contracts)
└── frontend/                       ← Next.js + msal.js
```

---

## 6. Naming Conventions

- **Azure resource names:** `medisync-<env>-<service>-<thing>` for non-globally-unique resources (e.g., `medisync-prod-match-func`). For globally-unique resources (Storage Accounts, Cosmos accounts, Key Vaults), use a 3–5 char suffix to disambiguate: `medisyncprodmatchst01` (Storage Accounts must be lowercase, 3–24 chars, no dashes).
- **Tags on every Azure resource:** `Project=MediSync`, `Environment=prod|dev`, `ManagedBy=Terraform`, `Service=<service-name>`. Used for cost allocation and RBAC conditions.
- **Cosmos DB:** one account per environment, one database per service, **single container per service** when access patterns are bounded. `id`/`partitionKey` naming follows the same intent as the original DynamoDB PK/SK from spec.md §3.
- **Event Grid `eventType`:** PascalCase past-tense, e.g., `MediSync.EmergencyRequestCreated`, `MediSync.MatchFound`, `MediSync.MatchFailed`, `MediSync.ReservationReleased`. Namespace prefix (`MediSync.`) is the convention for custom event types.
- **Function names:** `<verb><Noun>` (PascalCase function-level), Function App name `medisync-<env>-<service>-func`.
- **Python:** `snake_case`, type hints required, Pydantic for all I/O boundaries.
- **TypeScript:** `camelCase` for vars, `PascalCase` for components/types.
- **Git branches:** `feat/<short-slug>`, `fix/<short-slug>`. Commits: conventional commits (`feat:`, `fix:`, `chore:`).

---

## 7. Environment Variables

Each Function App gets these. Values live in Key Vault; Function App "Application settings" reference them via `@Microsoft.KeyVault(SecretUri=...)`; locally they live in `local.settings.json` (gitignored) or a `.env` (gitignored, loaded by `func start`).

```
# Common
AZURE_REGION=southeastasia
ENV=dev|prod
LOG_LEVEL=INFO
SERVICE_NAME=user|inventory|match
APPLICATIONINSIGHTS_CONNECTION_STRING=

# User service
ENTRA_TENANT_ID=
ENTRA_CLIENT_ID=
COSMOS_ENDPOINT=
COSMOS_USER_DB=
COSMOS_USER_CONTAINER=

# Inventory service
COSMOS_INVENTORY_DB=
COSMOS_INVENTORY_CONTAINER=

# Match service
COSMOS_REQUEST_DB=
COSMOS_REQUEST_CONTAINER=
EVENTGRID_TOPIC_ENDPOINT=
DURABLE_TASK_HUB_NAME=

# Local dev only
COSMOS_EMULATOR_ENDPOINT=https://localhost:8081
AZURE_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true
```

**Never commit `local.settings.json` or `.env`.** A `local.settings.example.json` per service documents required keys.

---

## 8. Patterns — How To Implement Them

### Saga (Match service) — Durable Functions
- **Orchestrator function** triggered by Event Grid event `EmergencyRequestCreated`.
- **Activity functions:** `FindInventoryActivity` → `ReserveActivity` → `NotifyActivity` → `CompleteActivity`. Each activity is a pure Azure Function call.
- **Compensation:** orchestrator wraps activities in `try/except`. On failure, calls `ReleaseReservationActivity`, which publishes `ReservationReleased` event to Event Grid for auditability.

### Optimistic locking (Inventory reserve) — Cosmos DB ETag
```python
# Read with ETag, mutate, write with If-Match
item = container.read_item(item="INV#{inv_id}", partition_key=inv_id)
etag = item["_etag"]
item["status"] = "Reserved"
item["reserved_by"] = request_id
container.replace_item(
    item="INV#{inv_id}",
    body=item,
    etag=etag,
    match_condition=MatchConditions.IfNotModified,
)
# Catch CosmosAccessConditionFailedError -> 409 to caller
```

### Geo matching (Inventory)
- On write, compute geohash from lat/lng (use `pygeohash` or compute inline).
- Store `geohash` and `geohash_prefix` (length 5 ≈ 5 km) as item properties.
- Cosmos query: `SELECT * FROM c WHERE c.geohash_prefix = @gh`, partition key = `geohash_prefix`. Then filter by exact distance in Python.

### RBAC
- **Entra External ID** application defines app roles (`Hospital`, `Donor`, `Courier`, `Doctor`).
- Frontend MSAL.js requests tokens with the relevant scope.
- Function HTTP trigger validates the JWT (signed by Entra) via `azure-functions` middleware or manual `python-jose` decode.
- Python dependency re-reads the `roles` claim and enforces per-endpoint.

### Tracing
- `azure-monitor-opentelemetry` configures OpenTelemetry to export traces to Application Insights with one call.
- Every Function App has the `APPLICATIONINSIGHTS_CONNECTION_STRING` env var set.
- One README screenshot of a cross-service Application Map / End-to-End transaction is a Phase-1 deliverable.

---

## 9. Definition of Done — Per PR

A PR is mergeable only if:
- [ ] `pytest` passes for affected services.
- [ ] `ruff check` and `ruff format --check` pass.
- [ ] `terraform fmt -check` and `terraform validate` pass.
- [ ] No new Azure resource outside the banned-services list (§2.1).
- [ ] No new RBAC role assignment broader than needed (no `Contributor` on subscription; no `Owner` ever).
- [ ] If a new env var is added, `local.settings.example.json` updated.
- [ ] If a new event type is added, Pydantic schema added in `packages/shared/`.

---

## 10. MCP Servers (the agent's eyes into Azure)

Configured in `.claude/settings.json` (separate deliverable). The agent has read-mostly access to Azure via:

| MCP | What the agent does with it |
|---|---|
| Azure MCP server (preview) / `az` CLI | Inspect any Azure resource via the `medisync-admin` SP |
| Cost Management via Azure CLI | Verify spend before/after changes; warn user proactively |
| Log Analytics via Azure CLI (`az monitor log-analytics query`) | Pull Function logs when debugging |
| Cosmos DB SDK in agent | Inspect items, run point reads during dev |
| GitHub MCP | PR status, CI runs, issues |
| Context7 / Ref | Live Azure SDK + Functions docs |

**RBAC scope for the agent's identity:** read-only on most services via the `medisync-admin` SP. The agent never has data-plane write outside dev environments. Production writes always go through Terraform + GitHub Actions OIDC — the SP cannot deploy.

---

## 11. Cost Discipline (repeat from rules; this matters)

- **Before adding any Azure resource**, the agent should mentally check: "Is this in §4? Is it free-tier? Is it in the banned list (§2.1)?"
- **When in doubt about cost**, run `az consumption usage list` (or read Cost Management Budget burn) and report the current month's spend to the user before applying.
- **Suspicious signs to flag:** any resource with "Premium", "Standard" (with sizing), "Dedicated", "Provisioned", "Reserved", or specific SKU tiers (S1, P1, etc.) — most paid SKUs include those. Consumption / Serverless / Free tiers should be the explicit default.

---

## 12. Pointers to Other Files

- **`spec.md`** — original tech spec. Sections §2, §3, §5, §7 still apply conceptually; vendor choices in §2 and §4 are overridden by §3 and §4 of *this* file.
- **`Requirement.md`** — vision and "why." Use the framing language for the README.
- **`use_case.md`** — the "Golden Hour" narrative. Use this verbatim for interview prep and the README story.
- **`docs/runbooks/`** — versioned one-time setup procedures (account bootstrap, RBAC, tooling).
- **`docs/_archive/context-aws.md`** — the AWS-era context, preserved for reference and for comparing architectural decisions across vendors.
- **`C:\Users\Admin\.claude\plans\i-need-you-to-sorted-pearl.md`** — the original approved build plan with milestones M0–M5 (AWS-flavored; pending re-write).

---

## 13. When the Agent Is Unsure

Stop and ask the user. Specifically ask before:
- Provisioning anything outside the §4 list.
- Adding a new third-party paid service.
- Modifying RBAC role assignments that touch billing, subscription, or tenant settings.
- Running `terraform apply` against `prod`.
- Upgrading the subscription from Free Trial to Pay-As-You-Go (this removes the spending-limit safety net).

Local file edits, scaffolding, writing Function handlers, writing tests, editing Terraform without applying — proceed without asking.
