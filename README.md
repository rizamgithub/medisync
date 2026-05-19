# MediSync — Decentralized Emergency Blood & Organ Supply Chain

> **Status:** 🚧 Under active development. Cloud-native event-driven platform on **Microsoft Azure**, built as a portfolio piece demonstrating senior-level serverless architecture, distributed-transaction patterns, IaC, and observability.

---

## The problem

In many regions, hospitals, blood banks, and donors operate in information silos. When a patient needs an emergency transfusion of a rare blood type, the only escalation path is often **a nurse spending 30 minutes on the phone calling other hospitals**, or families posting WhatsApp pleas. There is no real-time, automated system that matches inventory to demand inside the **golden hour** that determines survival.

## The solution

**MediSync** is an event-driven microservices platform that:

1. **Tracks blood/organ inventory** across registered hospitals in real time.
2. **Matches emergency requests** to the nearest stocked location automatically (geohash-indexed search).
3. **Falls back to a donor broadcast** when no hospital has stock — notifying eligible donors within a 10 km radius.
4. **Orchestrates a distributed Saga** across inventory reservation → courier dispatch → confirmation, with automatic compensation on failure.
5. **Maintains an audit trail** of every transfer for transparency and analytics.

→ Read the full ["Golden Hour" use-case narrative](./use_case.md) for the actor-by-actor walkthrough.

---

## Architecture (Phase 1)

> *Architecture diagram coming soon — placeholder for `docs/diagrams/architecture.png`*

```
┌─ Next.js Frontend (Static Web Apps) ──────────────────┐
│  MSAL.js → Entra External ID                          │
└─────────────────────┬─────────────────────────────────┘
                      │ HTTPS + JWT
┌─────────────────────▼─────────────────────────────────┐
│   Function App: user      Function App: inventory     │
│   (Auth, profile CRUD)    (Stock, geohash query)      │
└──────┬───────────────────────────────┬────────────────┘
       │                               │
       │           Event Grid           │
       │       (EmergencyRequestCreated,│
       │        MatchFound, MatchFailed,│
       │        ReservationReleased)    │
       │                               │
┌──────▼───────────────────────────────▼────────────────┐
│  Function App: match (Durable Functions Saga)         │
│  Orchestrator → FindInventory → Reserve → Notify      │
│       └──── compensation: ReleaseReservation ─┐       │
└──────────────────────────────────────────────┘ │      │
                                                │      │
┌─ Cosmos DB for NoSQL (serverless) ──────────┘ │      │
│   user / inventory / request / event-log          │
└────────────────────────────────────────────────────┘
                      │
                      ▼
              Application Insights
            (distributed tracing, KQL)
```

---

## Tech stack

| Layer | Service |
|---|---|
| Compute | **Azure Functions** (Python 3.12, consumption plan, v2 programming model) |
| Orchestration | **Durable Functions** for the Saga |
| NoSQL data | **Cosmos DB for NoSQL** (serverless mode — 1000 RU/s + 25 GB free always) |
| Eventing | **Azure Event Grid** (custom topics) |
| Auth | **Entra External ID** (formerly Azure AD B2C) — 50k MAU free |
| Email | **Azure Communication Services — Email** |
| Frontend | **Next.js 14** (TypeScript, App Router) on **Static Web Apps** |
| IaC | **Terraform** (`azurerm` v4) — state in Azure Storage |
| CI/CD | **GitHub Actions** with **OIDC federated credentials** (zero long-lived secrets) |
| Observability | **Application Insights** + **OpenTelemetry** (Python auto-instrumentation) |
| Logs | **Azure Monitor / Log Analytics** (KQL) |
| Identity | **Managed Identities** + **Key Vault** with Function App references |
| Cost guardrails | **Budgets + Action Groups** ($5 monthly cap, 50/80/100% email alerts) |

---

## Why these design decisions matter (interview-prep highlights)

**Saga Pattern with Durable Functions.** The Match service is a Durable orchestrator that wraps inventory reservation, courier dispatch, and notification in a single distributed transaction. If any step fails — say the courier service is down — the orchestrator runs a `ReleaseReservation` compensation activity that publishes a `ReservationReleased` event and unlocks the inventory item. Demo: I force the notify step to fail and screenshot the Durable Functions instance history showing the rollback. *(Coming soon.)*

**Optimistic concurrency via Cosmos DB ETag.** Two hospitals can never double-claim the same unit. Each reservation does a `replace_item` with `If-Match: <etag>`; the loser gets a `412 Precondition Failed` mapped to HTTP 409 to the caller.

**Geohash partition strategy on Cosmos.** The inventory container uses `geohash_prefix` (length-5 ≈ 5 km) as its partition key. Radius queries hit a single logical partition and filter the final ring in Python. No PostGIS, no extension; just a string column.

**OIDC federated credentials, no long-lived secrets.** GitHub Actions authenticates to Azure via a federated credential on the `medisync-deploy` service principal. The repo holds three identifiers (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`) and zero secrets. If the repo is leaked, no Azure access leaks with it.

**Cost discipline.** The whole stack runs in the $0–$2/month band on Azure free tier. The hard cap is enforced by a $5 Cost Management Budget with 50/80/100% alerts. Free-trial spending limit stays ON.

---

## Phased delivery

- **Phase 1 (current):** Three services (user, inventory, match) communicating via Event Grid. Saga demo with screenshotted compensation. End-to-end Application Insights trace screenshot. `terraform destroy` verified clean.
- **Phase 2:** Logistics service — live courier tracking via **Azure SignalR Service** + Leaflet/OpenStreetMap map.
- **Phase 3:** Analytics — Kusto / Application Insights KQL aggregations for shortage prediction.

---

## Repo map

```
├── context.md          ← Authoritative tech reference for any agent or contributor
├── spec.md             ← Original technical spec (Azure-amended)
├── Requirement.md      ← Vision and "why"
├── use_case.md         ← "Golden Hour" narrative (interview-ready)
├── docs/
│   ├── runbooks/       ← Versioned one-time setup procedures
│   └── _archive/       ← Superseded design docs (AWS-era reference)
├── infra/              ← Terraform (azurerm)
├── services/           ← Function apps (user, inventory, match)
├── packages/shared/    ← Pydantic event schemas (typed contracts across services)
└── frontend/           ← Next.js + MSAL.js
```

---

## Origin note

This project was originally designed for **AWS** (Lambda, DynamoDB, EventBridge, Cognito, Step Functions). After an account suspension in May 2026, the entire stack was **ported to Azure equivalents** with the architectural patterns preserved intact. The AWS-era design documents are kept in [`docs/_archive/`](./docs/_archive/) for reference, and the migration itself is a useful demonstration that the architectural patterns (event-driven, Saga, optimistic concurrency, OIDC for CI, IaC) are **cloud-portable** when designed at the right abstraction.

---

## License

TBD.
