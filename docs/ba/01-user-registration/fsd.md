# FSD — User Registration & Authentication

| Field | Value |
|---|---|
| Feature ID | `01-user-registration` |
| Related BRD | [`brd.md`](./brd.md) |
| Related Flows | [`flows.md`](./flows.md) |
| Status | Draft |
| Last updated | 2026-05-24 |

---

## 1. Overview

This document specifies the **functional behavior** of MediSync's user registration, authentication and profile-management capability. It describes _what_ the system does; the BRD explains _why_. Where this FSD references HTTP routes or schemas, the source of truth is `services/user/app/routes.py` and `services/user/app/models.py`.

The feature spans three components:

- **Entra External ID** — hosted sign-up/sign-in user flow + JWT issuance.
- **User Function App** (`services/user/`) — owns the `Profile` document in the `profiles` Cosmos container; today runs `ANONYMOUS`, will validate JWTs.
- **Next.js frontend** (`frontend/`) — MSAL.js PKCE redirect flow + role-conditional UI.

Inventory and Match Function Apps are **consumers** of the JWT issued here; their auth changes are in scope for this feature (they must validate the token), but their domain endpoints are specified in their own future FSDs.

## 2. Actors

| Actor | Description | System role / RBAC |
|---|---|---|
| **Hospital** | Coordinator at a clinic/hospital. Submits emergency requests. | `Hospital` app role |
| **Donor** | Individual donor. Toggles availability, accepts reservations. Requires `blood_type`. | `Donor` app role |
| **Courier** | Logistics operator. Accepts pickup assignments. | `Courier` app role |
| **Doctor** | Clinical reviewer. Verifies and oversees. | `Doctor` app role |
| **Entra External ID** | Microsoft-hosted identity provider. Owns credentials, MFA, password reset, JWT issuance. | External system |
| **User Function App** | MediSync-owned profile store. Validates JWTs, owns `Profile` documents. | System-assigned Managed Identity → `Cosmos DB Built-in Data Contributor` on the `profiles` container |
| **Inventory / Match Function Apps** | Downstream consumers. Validate the same JWT, read `roles` and `oid` claims. | Their own Managed Identities; do **not** call the User Function App |
| **Cosmos DB (`profiles` container)** | System of record for MediSync-owned profile fields. | Partition key `/id` |

## 3. Use Cases

### UC-01: New user signs up

| Field | Value |
|---|---|
| ID | UC-01 |
| Primary actor | Unauthenticated visitor (becomes Hospital / Donor / Courier / Doctor) |
| Secondary actors | Entra External ID, User Function App, Cosmos DB |
| Preconditions | Visitor has a valid email address. The Entra External ID tenant is provisioned and the user flow is published. |
| Trigger | Visitor clicks "Sign up" on the MediSync landing page. |
| Postconditions (success) | (a) Entra has a verified user with one app-role assignment; (b) the `profiles` container has a `Profile` document keyed by Entra `oid`; (c) the browser holds a valid access token and is redirected to the role-appropriate dashboard. |
| Postconditions (failure) | No `Profile` row is created. Entra may have a half-completed user; visitor can retry sign-in to resume. |

**Main flow**

1. Visitor clicks "Sign up" → frontend triggers MSAL `loginRedirect` with PKCE.
2. Browser is redirected to the Entra-hosted sign-up page.
3. Visitor enters email, password, display name, and selects one role (`Hospital` / `Donor` / `Courier` / `Doctor`). Donors additionally select a blood type from the eight options in `BloodType`.
4. Entra sends an email-verification code; visitor enters it.
5. Entra creates the directory user, assigns the chosen app role, and redirects the browser back to `https://<frontend>/auth/callback` with an authorization code.
6. MSAL exchanges the code (PKCE) for an access token + ID token; tokens are cached in session storage.
7. Frontend calls `POST /api/auth/signup` with `Authorization: Bearer <token>` and a body matching `SignupRequest` (the role-specific fields the visitor provided).
8. User Function App validates the JWT, extracts `oid` and `roles`, validates the body against `SignupRequest`, builds a `Profile` (with `id = oid`) via `Profile.from_signup`, and persists it via `ProfileRepository.create`.
9. Function returns `201 Created` with the serialized `Profile`.
10. Frontend redirects to the role-appropriate dashboard (`/inventory` for Donor/Courier, `/request` for Hospital, `/status` for Doctor).

**Alternate flow — A1: Donor omits blood type**

3a. The Entra user flow requires a blood-type selection when role = Donor; the hosted page enforces this client-side. If a payload nonetheless reaches `/api/auth/signup` with `role=Donor` and no `blood_type`, the `SignupRequest` model validator rejects with `422 Unprocessable Entity` and a structured `details` list pointing at the missing field.

**Alternate flow — A2: Returning user clicks "Sign up"**

5a. If Entra recognizes the email as an existing user, the hosted page offers "sign in instead." The flow continues as UC-02 from step 3.

**Exception flow — E1: Cosmos write fails after Entra user is created**

8e. If `create_item` raises (transient Cosmos error, RBAC misconfiguration, container missing), the Function returns `500` with a correlation ID. The user exists in Entra but has no `Profile`. UC-04 (first-sign-in self-heal) handles this: on next successful sign-in, if no `Profile` exists for the `oid`, the frontend re-invokes `POST /api/auth/signup` using profile fields read from the ID token claims plus a minimal "complete your profile" form for role-specific fields.

**Exception flow — E2: Email-verification code expires**

4e. Entra's hosted page handles this and offers "send a new code." No MediSync code involvement.

---

### UC-02: Returning user signs in

| Field | Value |
|---|---|
| ID | UC-02 |
| Primary actor | Existing user of any role |
| Secondary actors | Entra External ID, User Function App |
| Preconditions | User has previously completed UC-01 and has a `Profile` document. |
| Trigger | User clicks "Sign in" on the landing page or is redirected from a protected page. |
| Postconditions (success) | Browser holds a valid access token; user lands on the role-appropriate dashboard. |
| Postconditions (failure) | No token; user remains on the landing page with an error banner. |

**Main flow**

1. User clicks "Sign in" → MSAL `loginRedirect`.
2. Entra hosted sign-in page collects email + password.
3. Entra issues access token + ID token containing `oid`, `email`, `name`, `roles`.
4. Browser is redirected back to `/auth/callback`; MSAL caches the tokens.
5. Frontend calls `GET /api/users/{oid}` (the `oid` from the token) to load the profile.
6. User Function App validates the JWT, returns the `Profile` JSON.
7. Frontend renders the role-appropriate dashboard.

**Alternate flow — A1: Profile missing for known Entra user**

6a. If `GET /api/users/{oid}` returns `404`, frontend redirects to the "complete your profile" page (see UC-01 exception E1) and posts to `POST /api/auth/signup` to materialize the `Profile`.

**Exception flow — E1: Token expired between page loads**

5e. User Function App returns `401 Unauthorized`. Frontend uses MSAL's silent token refresh; if refresh fails, redirects to `loginRedirect`.

---

### UC-03: User updates their profile

| Field | Value |
|---|---|
| ID | UC-03 |
| Primary actor | Any authenticated user (typically Donor toggling `is_available`, or any user editing `display_name` / `location`) |
| Secondary actors | User Function App, Cosmos DB |
| Preconditions | User is signed in and holds a valid token. A `Profile` exists for their `oid`. |
| Trigger | User submits a profile-edit form, or clicks the "Available / Unavailable" toggle. |
| Postconditions (success) | `Profile` document reflects the change; `updated_at` is bumped. |
| Postconditions (failure) | No state change. UI surfaces the rejection reason. |

**Main flow**

1. Frontend reads the current `Profile` (already cached from UC-02 step 5).
2. User changes one or more fields. Form constructs a `ProfileUpdate` body containing **only the changed fields**.
3. Frontend calls `PATCH /api/users/{user_id}` with the JWT and the partial body.
4. User Function App validates JWT, validates body against `ProfileUpdate`, calls `ProfileRepository.update`.
5. Repository performs a read-modify-write guarded by `If-Match: <etag>` (Cosmos `MatchConditions.IfNotModified`).
6. Function returns `200 OK` with the updated `Profile`.

**Alternate flow — A1: Concurrent update conflict**

5a. If another writer modified the document between read and write, Cosmos raises `CosmosAccessConditionFailedError`. Repository raises `ProfileVersionConflictError`. Function returns `409 Conflict` with `{"error": "Profile was modified concurrently — retry", "user_id": "<id>"}`. Frontend re-fetches the profile (`GET /api/users/{user_id}`) and re-applies the user's change atop the fresh document.

**Alternate flow — A2: Empty body**

3a. If the request body has no updatable fields (`ProfileUpdate.is_empty()`), the Function returns `400 Bad Request` with `"Request body contains no updatable fields"`. (This catches a frontend bug, not a user mistake.)

**Exception flow — E1: Other user's profile**

4e. Even though the current code accepts any `user_id` in the URL, the authorized version of this endpoint enforces `user_id == token.oid`, otherwise `403 Forbidden`. (See §6 design note "Authorization rules.")

---

### UC-04: Frontend renders role-conditional UI

| Field | Value |
|---|---|
| ID | UC-04 |
| Primary actor | Any authenticated user |
| Secondary actors | None (purely client-side) |
| Preconditions | Frontend holds a valid access token containing the `roles` claim. |
| Trigger | User navigates to any protected page. |
| Postconditions (success) | The user sees only navigation entries, action buttons and forms appropriate to their role. |

**Main flow**

1. App-shell reads the `roles` claim from the cached token via MSAL.
2. Navigation component filters its menu items by role (e.g. only `Hospital` sees "New emergency request").
3. Each protected route also performs a server-side authorization check on its API calls; client-side hiding is UX, not security.

---

### UC-05: User signs out

| Field | Value |
|---|---|
| ID | UC-05 |
| Primary actor | Any authenticated user |
| Trigger | User clicks "Sign out." |
| Main flow | MSAL `logoutRedirect` clears the token cache and redirects through Entra's logout endpoint; browser lands back on the public landing page. |

---

## 4. User Stories

> Format: **As a** _{role}_, **I want** _{capability}_, **so that** _{benefit}_.

### US-01 — Hospital sign-up

**As a** Hospital coordinator,
**I want** to sign up for MediSync with my work email and select "Hospital" as my role,
**So that** I can start submitting emergency requests on behalf of my facility.

**Acceptance Criteria (Given / When / Then)**

- **Given** I am on the landing page and not signed in
  **When** I click "Sign up", complete the Entra hosted form (email, password, display name, role = `Hospital`) and verify my email
  **Then** I am redirected to the `/request` dashboard within 90 seconds and a `Profile` document exists in Cosmos with `id == my Entra oid`, `role == "Hospital"`, and `is_available == false`.

- **Given** I am on the Entra sign-up page
  **When** I select role = `Hospital`
  **Then** the form does **not** prompt me for a blood type.

- **Given** I am on the Entra sign-up page
  **When** I enter an invalid email format
  **Then** Entra blocks submission and shows an inline validation message; no request reaches MediSync.

---

### US-02 — Donor sign-up with blood type

**As a** Donor,
**I want** to register with my blood type as part of sign-up,
**So that** the matching service can find me for compatible emergency requests immediately.

**Acceptance Criteria**

- **Given** I am on the Entra sign-up page
  **When** I select role = `Donor`
  **Then** a "Blood type" field appears as required, with the eight valid options from `BloodType`.

- **Given** I have selected role = `Donor` and `blood_type = "O-"`
  **When** sign-up completes successfully
  **Then** my `Profile` document has `role == "Donor"`, `blood_type == "O-"`, and `is_available == true` by default.

- **Given** a malicious client bypasses the hosted UI and POSTs `{role: "Donor"}` without `blood_type` directly to `/api/auth/signup`
  **When** the request reaches the User Function
  **Then** the Function returns `422 Unprocessable Entity` with `details` pointing at the missing `blood_type` field.

- **Given** a malicious client POSTs `{role: "Hospital", blood_type: "A+"}`
  **When** the request reaches the User Function
  **Then** the Function returns `422` with a `details` entry explaining `blood_type may only be set when role is Donor`.

---

### US-03 — Returning user lands on the right dashboard

**As a** signed-up user,
**I want** signing in to take me straight to the dashboard for my role,
**So that** I don't have to navigate to find my work.

**Acceptance Criteria**

- **Given** I previously signed up as `Hospital`
  **When** I sign in
  **Then** I am redirected to `/request`.

- **Given** I previously signed up as `Donor` or `Courier`
  **When** I sign in
  **Then** I am redirected to `/inventory`.

- **Given** I previously signed up as `Doctor`
  **When** I sign in
  **Then** I am redirected to `/status`.

- **Given** my access token has expired
  **When** I open a protected page
  **Then** MSAL silently refreshes the token; if refresh fails, I am redirected to sign-in without seeing a 401 error toast.

---

### US-04 — Donor toggles availability

**As a** Donor,
**I want** to flip my availability on or off with one click,
**So that** I stop being matched when I am unavailable (work, travel, recent donation).

**Acceptance Criteria**

- **Given** I am signed in as Donor and `is_available == true`
  **When** I click the "Go unavailable" toggle
  **Then** the frontend sends `PATCH /api/users/{my_oid}` with body `{"is_available": false}` and the toggle updates within 500 ms on a 200 response.

- **Given** two browser tabs are open and tab A flips me to unavailable
  **When** tab B (which still holds the stale profile) tries to flip me back to available
  **Then** the API returns `409 Conflict`; tab B silently re-fetches my profile, sees `is_available == false`, applies its change to `true`, and retries. The final state is whatever the user clicked **last**.

- **Given** I send `PATCH /api/users/{my_oid}` with an empty body `{}`
  **When** the Function processes it
  **Then** I receive `400 Bad Request` with `"Request body contains no updatable fields"`.

---

### US-05 — Cross-role authorization

**As the** MediSync platform,
**I want** every protected endpoint to reject requests whose `roles` claim does not include the required role,
**So that** a Donor cannot create emergency requests and a Hospital cannot self-fulfill them.

**Acceptance Criteria**

- **Given** I am signed in as `Donor`
  **When** I call `POST /api/requests` (Match service)
  **Then** I receive `403 Forbidden`. The trace in App Insights records the rejection with `customDimensions.required_role == "Hospital"` and `customDimensions.actual_roles == ["Donor"]`.

- **Given** I am signed in as `Hospital`
  **When** I call `PATCH /api/inventory/{id}` (Inventory service)
  **Then** I receive `403 Forbidden`.

- **Given** I call any protected endpoint with no `Authorization` header
  **When** the JWT middleware runs
  **Then** I receive `401 Unauthorized`.

- **Given** I call a protected endpoint with a token whose signature does not validate against Entra's JWKS
  **When** the JWT middleware runs
  **Then** I receive `401 Unauthorized` and the rejection is logged **without** the token body.

---

### US-06 — Profile is private to its owner

**As a** signed-in user,
**I want** other users to be unable to read or modify my profile,
**So that** my email and location are not exposed.

**Acceptance Criteria**

- **Given** I am signed in with `oid == A`
  **When** I call `GET /api/users/{B}` for some `B != A`
  **Then** I receive `403 Forbidden`. (Admin override is out of scope; see BRD §6.)

- **Given** I am signed in with `oid == A`
  **When** I call `PATCH /api/users/{B}`
  **Then** I receive `403 Forbidden` before any Cosmos read.

---

### US-07 — Sign-out clears the session

**As a** user on a shared device,
**I want** signing out to remove my tokens,
**So that** the next person at the keyboard cannot resume my session.

**Acceptance Criteria**

- **Given** I am signed in
  **When** I click "Sign out"
  **Then** MSAL clears its token cache, the browser is redirected through Entra's `/logout` endpoint, and reloading any protected page redirects me to sign-in.

---

## 5. Non-functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | P50 time from "Sign up clicked" → first 2xx API response < 90s (includes email verification). P95 protected-endpoint latency < 500 ms excluding cold starts. JWT validation must be local (JWKS cached in-process, refreshed every 24h). |
| **Availability** | Inherits Azure Functions consumption-plan SLA (99.95%) and Entra External ID SLA (99.99%). No active redundancy required for Phase 1. |
| **Security** | All endpoints except `/api/health` require a valid Entra-issued JWT. JWT validation checks `iss`, `aud`, `exp`, and signature against Entra JWKS. No client secret is ever stored (SPA uses PKCE; APIs validate offline). PII fields (`email`, `display_name`, `location`) must never appear in log output — repository and route logging only references `id` and `role`. |
| **Observability** | Every request emits an App Insights trace with `customDimensions = { service, route, user_oid (hashed), role, result_code }`. The User Function App is connected to Application Insights via `APPLICATIONINSIGHTS_CONNECTION_STRING`. A cross-service "Application Map" screenshot is a Phase-1 deliverable. |
| **Cost** | Marginal monthly cost = **$0**. No new paid resources. Entra External ID free MAU tier, Cosmos serverless, Functions consumption. |
| **Compatibility** | Frontend supports the current stable Chrome, Edge, Firefox, Safari. Mobile-responsive (the dashboards already are). |
| **Accessibility** | The Entra hosted pages are Microsoft's responsibility. MediSync-owned pages (sign-up role picker, complete-profile, dashboards) target WCAG 2.1 AA — keyboard navigation and screen-reader labels on all form controls. |
| **Internationalization** | Phase 1: English only. The Entra user flow's language list is left at default. |

## 6. Data Contracts

All schemas are Pydantic v2 models in `services/user/app/models.py`.

### `SignupRequest`

```jsonc
{
  "email": "name@example.com",        // EmailStr, required
  "display_name": "Jane Smith",        // 1..120 chars, required
  "role": "Donor",                     // Hospital | Donor | Courier | Doctor
  "blood_type": "O-",                  // required iff role == "Donor", else forbidden
  "location": {"lat": 1.29, "lng": 103.85}  // optional; lat ∈ [-90,90], lng ∈ [-180,180]
}
```

Cross-field rule (`_blood_type_only_for_donors`):

- `role == "Donor"` requires `blood_type`.
- `role != "Donor"` forbids `blood_type`.

### `ProfileUpdate`

All fields optional; only present fields are applied. `extra="forbid"` rejects unknown keys.

```jsonc
{
  "display_name": "Jane S.",
  "location": {"lat": 1.29, "lng": 103.85},
  "is_available": true
}
```

`PATCH` rejects with `400` when the body has no updatable fields (`ProfileUpdate.is_empty()`).

### `Profile` (response + Cosmos document)

```jsonc
{
  "id": "<entra-oid-hex>",             // partition key; equals the Entra oid post-auth
  "email": "name@example.com",
  "display_name": "Jane Smith",
  "role": "Donor",
  "blood_type": "O-",                   // present only for Donors
  "location": {"lat": 1.29, "lng": 103.85},
  "is_available": true,                 // default true for Donor, false for others
  "created_at": "2026-05-24T10:00:00Z",
  "updated_at": "2026-05-24T10:00:00Z"
}
```

Cosmos system fields (`_etag`, `_rid`, `_ts`) are ignored on read (`extra="ignore"`).

### JWT claims consumed

| Claim | Source | Used as |
|---|---|---|
| `oid` | Entra | `Profile.id` and partition key |
| `email` | Entra | `Profile.email` on first signup |
| `name` | Entra | `Profile.display_name` on first signup |
| `roles` | Entra app-role assignment | Authorization on every protected endpoint |
| `iss`, `aud`, `exp` | Entra | Token validation |

### Cross-service event schemas

No new event types are emitted by this feature. (Subsequent features may emit `MediSync.UserRegistered` if downstream services need it; this is acknowledged debt, not Phase 1.)

## 7. Design Notes

These are decisions made while writing the FSD that the implementation must honor.

- **JWT validation library:** use `PyJWT` with a manually-cached JWKS rather than EasyAuth. Reason: EasyAuth couples Function App config to Entra-specific settings and obscures the token-validation step from a portfolio reviewer. A hand-rolled `azure-functions` middleware function that wraps each route is more demoable.
- **`Profile.id` strategy:** today `Profile.id` is a random UUID (`uuid4().hex`). Once Entra is wired in, `id` must equal the token's `oid` claim. This is a **breaking change to the seed/test data** but not to the wire format. Update path: `Profile.from_signup` accepts an optional `entra_oid` parameter; routes pass the validated `oid` in.
- **Authorization rules:** centralize as a decorator `@requires_role("Hospital")` and `@requires_owner_oid` (for `users/{user_id}` routes). Avoid scattering claim checks across route bodies.
- **PII logging:** `repository.py:45` currently logs `id` and `role` only — that pattern must be enforced everywhere. Add a `ruff` rule or PR-review checklist item.
- **`is_available` semantics:** `True` by default for Donors, `False` for everyone else (matches `Profile.from_signup`). Frontend only renders the toggle for Donors; the field is meaningless for other roles but is left writable for forward-compat (e.g. future Courier on-shift toggle).
- **Optimistic-locking UX:** on `409`, the frontend silently re-fetches and re-applies. The user does not see "conflict — retry"; they see their click eventually succeed. The error code is for developers, not end users.

## 8. Open Questions

- [ ] **Should `email` be allowed to change?** Currently `ProfileUpdate` does not permit it. Entra owns email; if it changes there, our `Profile.email` will drift. Decision: re-fetch from token on every sign-in and reconcile. Acknowledged debt.
- [ ] **Multi-role users?** Could one person be both Donor and Courier? Phase 1 enforces single-role at sign-up; the `roles` claim is an array though, so the schema can grow. Defer.
- [ ] **Role change after sign-up?** Out of scope for Phase 1 (BRD §6). Workaround: edit role via the Entra portal manually.
- [ ] **Soft delete vs hard delete?** Account deletion is out of scope. When added, should we tombstone or hard-delete the `Profile`? GDPR considerations push toward hard delete; audit considerations push toward tombstone. Open.
- [ ] **Rate limiting on `/api/auth/signup`?** Entra already throttles credential operations; our endpoint runs only after Entra issues a token, so abuse vectors are limited. Revisit if abuse appears.
