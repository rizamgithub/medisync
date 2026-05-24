# FSD — {{Feature Name}}

| Field | Value |
|---|---|
| Feature ID | `NN-feature-slug` |
| Related BRD | [`brd.md`](./brd.md) |
| Related Flows | [`flows.md`](./flows.md) |
| Status | Draft / Approved / Implemented |
| Last updated | YYYY-MM-DD |

---

## 1. Overview

Short summary of the functional behavior. Refer to the BRD for the "why."

## 2. Actors

| Actor | Description | System role / RBAC |
|---|---|---|
| e.g. Hospital | Submits emergency requests | `Hospital` app role |
| e.g. Donor | Registers availability | `Donor` app role |
| e.g. System (Match service) | Background matcher | Managed Identity |

## 3. Use Cases

### UC-01: {{Use Case Name}}

| Field | Value |
|---|---|
| ID | UC-01 |
| Primary actor | ... |
| Secondary actors | ... |
| Preconditions | ... |
| Trigger | ... |
| Postconditions (success) | ... |
| Postconditions (failure) | ... |

**Main flow**

1. Actor does X.
2. System validates Y.
3. System returns Z.

**Alternate flow — A1: {{condition}}**

1a. At step 2, if Y is invalid, system returns 400 with error code `ERR_...`.

**Exception flow — E1: {{condition}}**

1e. If downstream service unavailable, system queues for retry and returns 202.

---

### UC-02: ...

(repeat as needed)

---

## 4. User Stories

> Format: **As a** _{role}_, **I want** _{capability}_, **so that** _{benefit}_.

### US-01

**As a** Hospital coordinator
**I want** to submit an emergency blood request with patient blood type and urgency
**So that** the system can find a matching donor within the golden hour.

**Acceptance Criteria (Given / When / Then)**

- **Given** I am authenticated as a `Hospital` user
  **When** I POST a valid request with required fields
  **Then** the system returns `201 Created` with a `request_id` and emits `MediSync.EmergencyRequestCreated`.

- **Given** I am authenticated as a `Donor` user
  **When** I POST to the same endpoint
  **Then** the system returns `403 Forbidden`.

- **Given** the request payload is missing `blood_type`
  **When** I POST
  **Then** the system returns `400 Bad Request` with field-level validation errors.

---

### US-02: ...

(repeat as needed)

---

## 5. Non-functional Requirements

| Category | Requirement |
|---|---|
| Performance | e.g. p95 request latency < 500ms |
| Availability | e.g. tolerate single-region outage of dependent service |
| Security | e.g. JWT validation on every request; PII never logged |
| Observability | e.g. every request traced end-to-end in App Insights |
| Cost | e.g. zero idle cost — consumption plan only |

## 6. Data Contracts

Link to Pydantic schemas in `packages/shared/`:

- `EmergencyRequestCreated` → `packages/shared/events/emergency_request.py`
- ...

## 7. Open Questions

- [ ] ...
