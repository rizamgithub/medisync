> ## ⚠️ SUPERSEDED TWICE — Azure Edition (2026-05-19)
> This spec has been amended twice:
> 1. **2026-05-17** — original Fargate/RDS/IoT/AppSync design → **AWS serverless free-tier** (Lambda + DynamoDB + EventBridge + Step Functions).
> 2. **2026-05-19** — AWS account suspended → entire stack **pivoted to Azure**. Lambda → Azure Functions, DynamoDB → Cosmos DB serverless, EventBridge → Event Grid, Step Functions → Durable Functions, Cognito → Entra External ID, X-Ray → Application Insights, SES → Azure Communication Services. See `context.md` for the full mapping.
>
> **The architectural patterns (event-driven, Saga, RBAC, geo-matching, IaC, distributed tracing) are unchanged across all three iterations** — only the cloud vendor and the named services that implement them changed.
>
> **`context.md` at the project root is the authoritative source of truth.** Where this file or its AWS-era references conflict with `context.md`, `context.md` wins. The AWS-specific text below is preserved for historical reference; treat service names as illustrative, not prescriptive.
>
> **Headline changes:**
> - Compute: ECS Fargate → **AWS Lambda** (FastAPI via Lambda Web Adapter)
> - Inventory DB: RDS PostgreSQL → **DynamoDB** with geohash GSI (no PostGIS)
> - Realtime/IoT (Logistics): AppSync + IoT Core → **deferred to Phase 2** (API Gateway WebSockets when built)
> - Notifications: SNS+SMS → **SES email only** in Phase 1 (SMS deferred)
> - Analytics Service → **deferred to Phase 3**
> - Secrets Manager → **SSM Parameter Store** (free tier)
> - New: §0 Cost Strategy guardrails (below)
>
> ---

## 0. Cost Strategy (Non-Negotiable)

1. Dedicated AWS account for MediSync. Region: **`ap-southeast-1`** (Singapore).
2. CloudWatch billing alarm at **$1** — created day one before any other resource.
3. AWS Budget with **$5** hard cap and email alerts at 50/80/100%.
4. **Banned services in Phase 1:** RDS, Fargate, ECS, EKS, NAT Gateway, ALB, NLB, IoT Core, AppSync, OpenSearch, Kinesis Data Streams, MSK.
5. Everything scales to zero (Lambda + DynamoDB on-demand + EventBridge).
6. `terraform destroy` must always work cleanly.

---

This technical specification (The "Spec") outlines the requirements for **MediSync**. It is designed to be a "Medium Size" project—complex enough to show senior-level skills, but scoped tightly enough to complete in 4–6 weeks.

---

### 1. System Overview
MediSync is an event-driven microservices platform on AWS that connects hospitals in need of emergency blood/organs with nearby donors and inventory.

### 2. Microservices Definition

#### A. User & Identity Service  *(Phase 1)*
*   **Responsibility:** Authentication, Authorization, and User Profiles (Hospitals, Donors, Couriers, Doctors).
*   **Tech Stack:** **Python (FastAPI) on AWS Lambda** via Lambda Web Adapter, **AWS Cognito User Pools**, **DynamoDB** (single-table).
*   **Key Logic:**
    *   Store PII securely (Cognito-managed; profile attributes in DynamoDB).
    *   RBAC via Cognito groups + API Gateway JWT authorizer + FastAPI dependency re-check.

#### B. Inventory Service  *(Phase 1)*
*   **Responsibility:** Real-time tracking of blood units/organs across locations.
*   **Tech Stack:** **Python (FastAPI) on AWS Lambda**, **DynamoDB** with **geohash GSI** (replaces PostGIS).
*   **Key Logic:**
    *   CRUD for inventory items.
    *   Soft-reservation via **DynamoDB conditional write** (`ConditionExpression: status = :available`) — replaces row-level locking.

#### C. Match & Request Service (The Orchestrator)  *(Phase 1)*
*   **Responsibility:** Handling emergency requests and orchestrating matches.
*   **Tech Stack:** **Python (FastAPI) on AWS Lambda**, **Amazon EventBridge** (default bus), **Step Functions Express** for Saga orchestration.
*   **Key Logic:**
    *   Geo-hashing for distance ranking.
    *   **Saga Pattern** implemented as Step Functions Express workflow with `Catch` → compensation states (release reservation, publish `ReservationReleased`).

#### D. Notification Service  *(Phase 1 — email only)*
*   **Responsibility:** Email alerts for emergency match events.
*   **Tech Stack:** **Python on AWS Lambda**, **Amazon SES** (sandbox initially; production access requested before launch).
*   **Phase 1 scope:** Email only via SES. SMS (via SNS) and push notifications **deferred** — SMS requires paid SNS production access; push needs mobile app.

#### E. Logistics & Tracking Service  *(Phase 2 — deferred)*
*   **Responsibility:** Real-time location tracking of delivery.
*   **Original stack** (AppSync + IoT Core) **abandoned** — both are expensive and overkill for Phase 1.
*   **Phase 2 stack:** API Gateway **WebSockets** (cheap, scales to zero) + DynamoDB Streams + Leaflet/OpenStreetMap on frontend.

#### F. Analytics Service  *(Phase 3 — deferred)*
*   Originally specified in `Requirement.md`. Deferred to Phase 3 to keep portfolio scope tight.

---

### 3. Data Schema (Simplified)

**DynamoDB — User Table (`medisync-<env>-user`):**
*   `PK: USER#<ID>`, `SK: PROFILE`
*   Attributes: `Role`, `BloodType`, `GeoLocation`, `IsAvailable`.

**DynamoDB — Inventory Table (`medisync-<env>-inventory`):**  *(replaces PostgreSQL)*
*   `PK: INV#<id>`, `SK: ITEM`
*   Attributes: `hospital_id`, `item_type` (Blood/Organ), `sub_type` (O+, AB-), `expiry_date`, `status` (Available/Reserved/Dispatched), `lat`, `lng`, `geohash`, `geohash_prefix` (length 5 ≈ 5 km).
*   **GSI `geohash-index`:** PK = `geohash_prefix`, SK = `sub_type` — enables radius queries.

**DynamoDB — Request Table (`medisync-<env>-request`):**
*   `PK: REQ#<id>`, `SK: META` (and `SK: EVENT#<ts>` for audit trail).

**EventBridge (Event Schema — Pydantic-typed in `packages/shared/`):**
*   `DetailType: "EmergencyRequestCreated"` → `Detail: { requestId, hospitalId, location: {lat, lng}, bloodType, units, urgency }`
*   `DetailType: "MatchFound"` → `Detail: { requestId, inventoryId, hospitalId }`
*   `DetailType: "MatchFailed"` → `Detail: { requestId, reason }`
*   `DetailType: "ReservationReleased"` → `Detail: { requestId, inventoryId, reason }` *(Saga compensation)*

---

### 4. Infrastructure & DevOps Spec (The "Portfolio Gold")

*   **IaC:** **Terraform** (AWS provider). State in S3 + DynamoDB lock table. No manual console clicking.
*   **Compute packaging:** Each service is a FastAPI app packaged for **AWS Lambda** via the **Lambda Web Adapter** layer. Local dev runs the same FastAPI app under uvicorn. *(No Dockerfile/ECR/Fargate — those are banned per §0.)*
*   **API Gateway:** **HTTP API** (not REST API — cheaper and faster). Single entry point with JWT authorizer → Cognito. Routes: `/users/*`, `/inventory/*`, `/request/*`.
*   **Observability:**
    *   **AWS X-Ray** — tracing enabled on every Lambda; `aws-xray-sdk` patches boto3 + httpx.
    *   **CloudWatch Logs** — log group per Lambda, 7-day retention to stay in free tier.
*   **CI/CD:** **GitHub Actions** with **OIDC role assumption** (no long-lived AWS keys).
    *   On `push`: ruff lint + pytest + terraform validate.
    *   On `merge to main`: `terraform apply` against prod via OIDC role.

---

### 5. Essential API Endpoints

| Method | Endpoint | Service | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/signup` | User | Register a donor or hospital. |
| `GET` | `/inventory` | Inventory | View available stock in a region. |
| `POST` | `/request/emergency` | Match | Trigger an emergency search. |
| `GET` | `/track/:tripId` | Logistics | Get real-time GPS location via WebSocket. |

---

### 6. Security Requirements
1.  **Encryption at Rest:** All DynamoDB and RDS instances must have AES-256 encryption.
2.  **Encryption in Transit:** All traffic must be over HTTPS (TLS 1.2+).
3.  **Secrets Management:** Use **AWS SSM Parameter Store** `SecureString` (free tier) for config and secrets. *(Secrets Manager avoided — charges $0.40/secret/month.)* Never hardcode credentials.
4.  **Least Privilege:** IAM roles for Lambda/ECS must only have the exact permissions they need (e.g., Inventory service cannot access the Donor's medical history).

---

### 7. Definition of Done (Portfolio Milestone)
To consider this project complete for your portfolio, you must have:
1.  **A live ReadMe:** Explaining the architecture and including the diagram.
2.  **Three services running:** Communicating via EventBridge (Asynchronous).
3.  **The Saga demo:** Force a failure in the notify step → screenshot the Step Functions execution showing the `ReleaseReservation` compensation running and the DynamoDB item returning to `Available`. *(Live-Map demo moves to Phase 2.)*
4.  **A Clean Cleanup Script:** `terraform destroy` wipes all infrastructure cleanly — verified $0 footprint in Cost Explorer the next day.
5.  **X-Ray cross-service trace screenshot** in the README.

**Phase 2 (Definition of Done):** Add Logistics service + Live Map (API Gateway WebSockets + Leaflet/OSM).