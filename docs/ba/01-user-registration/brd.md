# BRD — User Registration & Authentication

| Field | Value |
|---|---|
| Feature ID | `01-user-registration` |
| Author | Rizam |
| Date created | 2026-05-24 |
| Last updated | 2026-05-24 |
| Status | Draft |
| Related FSD | [`fsd.md`](./fsd.md) _(pending)_ |
| Related Flows | [`flows.md`](./flows.md) _(pending)_ |

---

## 1. Executive Summary

MediSync coordinates emergency blood and organ supply across hospitals, donors, couriers and doctors. Before any matching, reservation or delivery can happen, the platform needs to know **who** is acting and **what role** they hold. This feature delivers the foundational capability for the four MediSync personas — Hospital, Donor, Courier, Doctor — to **sign up**, **sign in**, and **maintain a profile** that downstream services (Inventory, Match) can trust as the authoritative source of identity and role.

Authentication is delegated to **Microsoft Entra External ID** (50k MAU free tier); profile data is owned by the **User Service** (Azure Functions + Cosmos DB). Together they give every request in the system a verified actor and a role claim that the Match Saga, Inventory reservations and audit log can rely on.

## 2. Business Context

MediSync's value proposition — solving the "Golden Hour" problem in emergency supply — depends on **trust**. A hospital coordinator triggering a blood-type-O request must be a real, verified hospital. A donor accepting a reservation must be reachable. A courier confirming pickup must be the assigned one. Without verified identity:

- The matching algorithm cannot enforce role-based eligibility (a donor cannot create a request; a hospital cannot self-fulfill).
- The audit trail required for clinical/regulatory accountability has no actor to attribute events to.
- Notifications (email via Azure Communication Services) have no addressable recipient.
- The portfolio narrative loses credibility — recruiters reviewing the repo expect to see real auth, not stubs.

The current state of the codebase reflects this gap: `services/user/app/routes.py` runs at `authLevel="ANONYMOUS"` with a `TODO(entra)` marker, and `infra/identity.tf` is a placeholder. This BRD scopes the work to close that gap end-to-end.

## 3. Problem Statement

**Today**, the User Service exposes signup/profile endpoints with no authentication, no role enforcement, and no link to a customer identity provider. Downstream services therefore cannot tell which role is calling them, and the platform cannot safely be exposed beyond local development.

**When this feature exists**, the problem is solved because:

1. A new user can self-register through a hosted, branded sign-up page and receive a verified account in Entra External ID.
2. A `Profile` document is created in the `profiles` Cosmos container at first sign-in, keyed to the Entra `oid` (object ID).
3. Every protected endpoint across User, Inventory and Match validates the Entra-issued JWT and reads the `roles` claim before authorizing the request.
4. A returning user can sign in with email + password (or social login if enabled), receive an access token via MSAL.js, and call the API from the Next.js frontend.

## 4. Stakeholders (RACI)

| Stakeholder | Role | R | A | C | I |
|---|---|:-:|:-:|:-:|:-:|
| Hospital coordinator | End user — submits emergency requests | ✓ |   | ✓ |   |
| Donor | End user — registers availability, accepts reservations | ✓ |   | ✓ |   |
| Courier | End user — accepts pickup assignments | ✓ |   | ✓ |   |
| Doctor | End user — clinical oversight, verification | ✓ |   | ✓ |   |
| Rizam (Product Owner / Engineer / BA) | Decides scope, builds, accepts |   | ✓ | ✓ |   |
| Recruiters / interviewers | Portfolio reviewers — downstream consumer of the narrative |   |   |   | ✓ |
| Entra External ID (Microsoft) | Identity provider — verifies credentials, issues tokens | ✓ |   |   |   |
| Azure Cost Management | System — enforces $5 budget |   |   | ✓ | ✓ |

(R = Responsible, A = Accountable, C = Consulted, I = Informed)

## 5. Business Goals & Success Metrics

| # | Goal | Metric | Target | How measured |
|---|---|---|---|---|
| G1 | Every API call has a verified actor | % of non-health protected requests with a valid JWT | 100% | App Insights query: requests where `customDimensions.auth_status != "valid"` should be 0 (excluding `/api/health`) |
| G2 | Role-based access is enforced | Requests rejected for missing role | All cross-role attempts return `403` | Manual test matrix + App Insights `resultCode=403` filtered by role mismatch trace |
| G3 | Sign-up to first authenticated API call is fast | P50 time from "Sign up clicked" to "first 2xx API response" | < 90 seconds | App Insights end-to-end transaction trace |
| G4 | Auth cost stays at zero | Monthly Entra External ID + ACS Email charges | $0 | Cost Management Budget burn for `Service=user` tag |
| G5 | The auth story is demoable on the portfolio | A reviewer can sign up at the live URL and reach the dashboard | 1 working flow | Manual smoke test recorded as a 60-second screen capture in the README |
| G6 | Zero secret leakage in repo | Entra `client_secret` or comparable credential committed to git | 0 occurrences | GitHub push-protection + `gitleaks` CI check |

## 6. Scope

### In scope

- A new **Entra External ID tenant** (separate from the workforce tenant) with two app registrations: one **API** identity (audience for tokens) and one **SPA** identity (Next.js frontend).
- A **sign-up / sign-in user flow** in Entra External ID supporting email + password, with email verification.
- Four **app roles** defined on the API app registration: `Hospital`, `Donor`, `Courier`, `Doctor`. The role is selected at sign-up and stored as an Entra app-role assignment.
- A **Profile document** created in the `profiles` Cosmos container on first sign-in, keyed by Entra `oid`. Fields: `oid`, `email`, `display_name`, `role`, `created_at`, `updated_at`, plus role-specific fields (e.g. `blood_type` for Donor, `hospital_name` for Hospital).
- **JWT validation middleware** in the three Function Apps (User, Inventory, Match) that:
  - validates token signature against Entra JWKS,
  - verifies `iss`, `aud`, `exp`,
  - extracts the `roles` claim into the request context.
- A **frontend sign-up / sign-in experience** using MSAL.js with PKCE, redirecting through the Entra hosted pages.
- A **profile read & partial-update endpoint** (`GET` / `PATCH /api/users/{user_id}`) with Cosmos ETag optimistic locking for concurrent writes.
- All resources defined in **Terraform** (`infra/identity.tf`, `infra/functions.tf` for the User Function App, role assignments for the Managed Identity to Cosmos).
- The runbook (`docs/runbooks/10-entra-external-id.md`) covering the one-time portal steps to bootstrap the external tenant.

### Out of scope (explicit non-goals)

- Multi-factor authentication (deferred — Entra External ID supports it as a future toggle).
- Social identity providers (Google, Apple, Microsoft personal accounts). The user flow only enables email + password initially.
- Self-service password reset flows beyond what the Entra hosted page provides by default.
- Profile fields beyond the minimum needed for matching and notification. Avatars, address books, preferences are out.
- Admin / back-office user management UI. Role changes happen via the Entra portal in Phase 1.
- Account deletion / GDPR data-subject endpoints — acknowledged debt for Phase 2.
- Verification of real-world credentials (e.g. confirming a "Hospital" account is actually a licensed hospital). This is a trust model decision deferred to Phase 2; Phase 1 treats role self-selection as honest-but-unverified.
- Audit logging of authentication events beyond what App Insights captures by default.

## 7. Assumptions

- The free tier of Entra External ID (50,000 MAU) is sufficient — a portfolio project will not approach it.
- The user owns the workforce tenant `rizamibrahimmygmail.onmicrosoft.com` and is Global Admin (confirmed in runbook 10).
- The SPA uses the public-client PKCE flow; **no client secret** is needed (this is the architectural reason no auth credential ever needs to be stored in repo or Key Vault for the frontend).
- All three Function Apps validate tokens **offline** against the published JWKS endpoint — no per-request call to Entra.
- The frontend is served from Azure Static Web Apps under a known origin that can be added to Entra's redirect-URI allowlist.
- The `profiles` Cosmos container will be created in the existing dev Cosmos account; serverless tier accommodates the expected load.

## 8. Constraints

### Technical

- Must operate within the banned-services list in `context.md` §2.1 — no App Service Plan upgrades, no API Management, no premium SKUs.
- Auth must work end-to-end without storing any long-lived client secret in CI or repo (`context.md` §2.4).
- All resources provisioned via Terraform; portal clicks are confined to one-time bootstrap documented in `docs/runbooks/10-entra-external-id.md`.
- Function Apps run on consumption Linux plan; cold-start latency for first auth call is acceptable (< 3s).
- Token validation must use `azure-identity` + `PyJWT` against JWKS (no third-party paid services).
- All PII fields (`email`, `display_name`, `phone`) must be excluded from log output.

### Regulatory / Compliance

- Portfolio project, no live PHI / PII of real patients. Test data only.
- If real users ever sign up (e.g. recruiter demo accounts), email addresses are the only PII collected and they remain inside Entra's data boundary.

### Time / cost

- Target wall-clock effort: ~1 week of evening work.
- Marginal monthly cost: **$0** (Entra External ID free, Cosmos serverless free tier, Functions consumption free grant).

## 9. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Entra External ID tenant creation fails or takes longer than expected (Microsoft has occasionally had multi-hour provisioning delays) | M | M | Runbook 10 calls out the 30-minute provisioning window; if blocked > 24h, raise an Azure support ticket via the workforce tenant. |
| R2 | JWT validation library choice (`PyJWT` vs. `azure-functions` built-in EasyAuth) leads to refactor mid-build | M | L | Choose `PyJWT` + manual JWKS caching up-front; documented in the FSD's design notes. EasyAuth is appealing but couples the Functions to Entra-specific config rather than a portable JWT check. |
| R3 | Role claim is missing from the access token because the user wasn't assigned to an app role | M | H — silent 403s | Runbook 10 step 5 explicitly walks through enabling "User assignment required" + assigning the test user to a role. Smoke test in the FSD covers this. |
| R4 | A `client_secret` is accidentally created and committed | L | H — see [[feedback-secret-leak-lesson]] | SPA is a public client by design (PKCE, no secret). Runbook 10 explicitly states "This runbook produces no secrets." `gitleaks` runs in CI. |
| R5 | Cosmos ETag conflict on concurrent profile updates returns confusing UX | L | L | `PATCH /api/users/{user_id}` returns `409` with a structured body; frontend re-fetches and re-applies the user's change. FSD documents this. |
| R6 | Recruiter signs up at the live demo and sees a broken role-selection experience | L | M — portfolio damage | One end-to-end manual test recorded as a screen capture (Goal G5). Listed in the Phase-1 Definition of Done. |
| R7 | Frontend MSAL.js redirect URI mismatch on deploy (Static Web Apps preview URLs differ from prod) | M | M | Add both `https://<swa>.azurestaticapps.net` and any preview-slot pattern to the Entra redirect allowlist; document in runbook 10. |
| R8 | Profile schema changes break Inventory / Match consumers | L | M | The Pydantic `Profile` schema is centralized in `packages/shared/`; changes require updating consumers in the same PR. Enforced by `context.md` §9 DoD checklist. |

## 10. Dependencies

### Upstream (must exist before this feature can ship)

- Azure subscription with budget alerts in place (runbook 01 — done).
- Workforce tenant Global Admin access (the user's account — confirmed).
- Cosmos DB account provisioned (already created in `infra/cosmos.tf`).
- Terraform state backend (`infra/backend.tf` — done).

### Downstream (this feature unblocks)

- **Match service** — needs the `roles` claim to enforce that only `Hospital` users can `POST /api/requests`.
- **Inventory service** — needs `oid` to attribute reservations to a donor.
- **Frontend dashboards** — `/inventory`, `/request`, `/status` pages render role-conditional UI based on the token's `roles` claim.
- **Notification flow (future)** — needs `email` from the `Profile` to send pickup confirmations via Azure Communication Services.

## 11. Glossary

| Term | Definition |
|---|---|
| **Entra External ID** | Microsoft's customer-identity (CIAM) product — a separate tenant type from a workforce tenant, designed for external users (customers, partners). |
| **Workforce tenant** | The default Entra tenant tied to an organization's employees; here, `rizamibrahimmygmail.onmicrosoft.com`. |
| **App registration** | The identity record in Entra that represents an application — one for the API audience, one for the SPA client. |
| **App role** | A named permission (`Hospital`, `Donor`, `Courier`, `Doctor`) defined on an app registration and assignable to users; surfaces as the `roles` claim in issued tokens. |
| **User flow** | Entra External ID's hosted, branded sign-up / sign-in experience — a no-code policy that defines what attributes are collected and which identity providers are allowed. |
| **PKCE** | Proof Key for Code Exchange — the OAuth 2.0 extension that lets a public client (SPA) safely exchange an auth code for a token without a client secret. |
| **JWKS** | JSON Web Key Set — the public-key document Entra publishes for offline token signature verification. |
| **MSAL.js** | Microsoft Authentication Library for JavaScript — the frontend SDK that orchestrates the PKCE redirect flow. |
| **`oid`** | The Entra-issued, immutable object ID of a user — used as the partition key for the `Profile` document. |
| **Profile** | The MediSync-owned record (Cosmos document) that augments the Entra identity with domain attributes (`blood_type`, `hospital_name`, etc.). |
| **Optimistic locking** | Concurrency control where a write includes an `If-Match: <etag>` header; the server rejects with `412/409` if the document changed since read. |
| **MAU** | Monthly Active Users — the licensing unit for Entra External ID (50k free per tenant). |

## 12. Approvals

| Name | Role | Date | Signature |
|---|---|---|---|
| Rizam | Product Owner | _pending self-review_ |   |
| Rizam | Engineering Lead | _pending self-review_ |   |
| Rizam | Business Analyst | _pending self-review_ |   |
