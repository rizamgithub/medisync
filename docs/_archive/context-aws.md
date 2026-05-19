# MediSync — Agent Context

> **Read this first.** This file is the single source of truth for any AI agent (Claude Code, Cursor, Copilot, future me) working on this repo. If something here conflicts with the legacy `.md` specs, **this file wins** unless the user says otherwise.

---

## 1. What this project is

**MediSync** — an event-driven emergency blood/organ supply-chain platform. A portfolio project for the user (a software engineer building AWS credentials for job applications).

**Primary goal:** Get the user interviews. Optimize for:
- AWS keyword density (Lambda, DynamoDB, Cognito, EventBridge, Step Functions, IAM, CloudWatch, X-Ray, Terraform).
- Clean architecture patterns recruiters recognize (event-driven, Saga, RBAC, IaC, distributed tracing).
- A live demo that costs **$0–$2/month** to keep online.

**Secondary goal:** Be a real, working system the user can extend.

---

## 2. Non-Negotiable Rules

1. **No expensive AWS services in Phase 1.** Banned: RDS, Fargate, ECS, EKS, NAT Gateway, ALB, NLB, IoT Core, AppSync, OpenSearch, Kinesis Data Streams, MSK. If you think you need one, stop and ask.
2. **Everything scales to zero.** Lambda + DynamoDB on-demand + EventBridge. No always-on compute.
3. **100% Terraform.** Never create AWS resources via console clicks. If a resource exists in AWS that isn't in `infra/*.tf`, treat it as a bug.
4. **No long-lived AWS keys in CI.** GitHub Actions assumes an OIDC role.
5. **No hardcoded secrets.** SSM Parameter Store `SecureString` (free tier — do not use Secrets Manager, it charges per secret).
6. **Least-privilege IAM.** Every Lambda gets its own role with only the actions it needs. No `*` wildcards on actions or resources unless documented why.
7. **`terraform destroy` must always work.** If you add a resource that blocks destroy (S3 with objects, ECR with images, log groups with retention), add the cleanup to the destroy path.
8. **Cost alarm comes first.** Before any other AWS resource: CloudWatch billing alarm at $1, AWS Budget at $5 hard cap.

---

## 3. Stack

### Backend (per service)
- **Language:** Python 3.12
- **Framework:** FastAPI
- **Runtime on AWS:** Lambda, packaged with **AWS Lambda Web Adapter** (the FastAPI app is unchanged between local and Lambda).
- **Package manager:** `uv`
- **Validation/schemas:** Pydantic v2
- **AWS SDK:** `boto3`
- **Tracing:** `aws-xray-sdk` (auto-instrument boto3 + httpx)
- **Testing:** `pytest`, `moto` for AWS mocks, `httpx` for FastAPI test client

### Frontend
- **Framework:** Next.js 14+ (App Router), TypeScript
- **Hosting:** AWS Amplify Hosting
- **Auth client:** `aws-amplify` (Cognito Hosted UI)
- **Package manager:** `pnpm`

### Infrastructure
- **IaC:** Terraform (AWS provider)
- **State:** S3 backend + DynamoDB lock table (created once via a bootstrap script, then managed)
- **CI/CD:** GitHub Actions + OIDC

### Local dev
- **DynamoDB Local** (docker)
- **`docker-compose.yml`** runs all 3 FastAPI services + DynamoDB Local
- **`sam local`** is NOT used — local FastAPI via uvicorn is simpler

---

## 4. AWS Service Map

| Concern | Service | Free-tier note |
|---|---|---|
| Auth | Cognito User Pools | 50k MAU always free |
| All databases | DynamoDB (single-table where sensible) | 25 GB always free |
| Compute | Lambda (Python 3.12, arm64) | 1M req + 400k GB-s always free |
| HTTP edge | API Gateway HTTP API (not REST API — cheaper) | 1M req free 12 months |
| Events | EventBridge default bus | $1/M custom events |
| Saga | Step Functions **Express** workflows (not Standard) | 4k transitions/month free |
| Email | SES | 3k/month free; sandbox initially |
| Logs | CloudWatch Logs | 5 GB free always |
| Tracing | X-Ray | 100k traces/month free always |
| Secrets/config | SSM Parameter Store `SecureString` | free |
| Frontend host | Amplify Hosting | free 12 months |
| Cost monitoring | CloudWatch billing alarm + Budgets | free |

---

## 5. Repo Layout (target)

```
.
├── README.md                       ← public face: architecture, Saga story, live demo link
├── context.md                      ← THIS FILE
├── spec.md                         ← original spec (kept for history; serverless amendments applied)
├── Requirement.md                  ← original requirements (kept for history)
├── use_case.md                     ← "Golden Hour" narrative — interview-prep gold
├── docker-compose.yml              ← local dev: 3 FastAPI + DynamoDB Local
├── .claude/
│   └── settings.json               ← MCP server config
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── infra/                          ← Terraform
│   ├── main.tf
│   ├── backend.tf                  ← S3 + DynamoDB lock
│   ├── cognito.tf
│   ├── dynamodb.tf
│   ├── lambdas.tf
│   ├── api_gateway.tf
│   ├── eventbridge.tf
│   ├── stepfunctions.tf            ← Saga
│   ├── ses.tf
│   ├── observability.tf            ← X-Ray, log groups, billing alarm, budget
│   └── iam.tf
├── services/
│   ├── user/                       ← FastAPI; Cognito + profile DDB
│   ├── inventory/                  ← FastAPI; inventory DDB + geohash GSI
│   └── match/                      ← FastAPI; emits EventBridge events
├── packages/
│   └── shared/                     ← Pydantic event schemas (typed contracts)
└── frontend/                       ← Next.js + amplify-js
```

---

## 6. Naming Conventions

- **AWS resource names:** `medisync-<env>-<service>-<thing>` (e.g., `medisync-prod-inventory-table`).
- **Tags on every AWS resource:** `Project=MediSync`, `Environment=prod|dev`, `ManagedBy=Terraform`, `Service=<service-name>`. Used for cost allocation and IAM tag-based access control.
- **DynamoDB:** single-table per service when access patterns are bounded; `PK`/`SK` naming as in spec.md §3.
- **EventBridge detail-type:** PascalCase past-tense, e.g., `EmergencyRequestCreated`, `MatchFound`, `MatchFailed`, `ReservationReleased`.
- **Lambda function names:** `medisync-<env>-<service>-<handler>`, e.g., `medisync-prod-match-saga-handler`.
- **Python:** `snake_case`, type hints required, Pydantic for all I/O boundaries.
- **TypeScript:** `camelCase` for vars, `PascalCase` for components/types.
- **Git branches:** `feat/<short-slug>`, `fix/<short-slug>`. Commits: conventional commits (`feat:`, `fix:`, `chore:`).

---

## 7. Environment Variables

Each service gets these. Values live in SSM Parameter Store; Lambda env vars reference them; locally they live in `.env` (gitignored).

```
# Common
AWS_REGION=ap-southeast-1            # Singapore (confirmed; Malaysia ap-southeast-5 lacks SES + Amplify Hosting)
ENV=dev|prod
LOG_LEVEL=INFO
SERVICE_NAME=user|inventory|match

# User service
COGNITO_USER_POOL_ID=
COGNITO_CLIENT_ID=
USER_TABLE_NAME=

# Inventory service
INVENTORY_TABLE_NAME=
GEOHASH_GSI_NAME=

# Match service
REQUEST_TABLE_NAME=
EVENT_BUS_NAME=default
SAGA_STATE_MACHINE_ARN=

# Local dev only
DYNAMODB_ENDPOINT=http://dynamodb-local:8000
```

**Never commit `.env`.** A `.env.example` per service documents required keys.

---

## 8. Patterns — How To Implement Them

### Saga (Match service)
- Step Functions **Express** state machine.
- Triggered by EventBridge rule on `EmergencyRequestCreated`.
- States: `FindInventory` → `Reserve` → `Notify` → `Complete`. Each has a `Catch` to a compensation state (`ReleaseReservation`).
- Compensation publishes `ReservationReleased` event for auditability.

### Optimistic locking (Inventory reserve)
```python
table.update_item(
    Key={"PK": f"INV#{inv_id}", "SK": "ITEM"},
    UpdateExpression="SET #s = :reserved, reserved_by = :rid",
    ConditionExpression="#s = :available",
    ExpressionAttributeNames={"#s": "status"},
    ExpressionAttributeValues={
        ":available": "Available",
        ":reserved": "Reserved",
        ":rid": request_id,
    },
)
# Catch ClientError ConditionalCheckFailedException → 409 to caller
```

### Geo matching (Inventory)
- On write, compute geohash from lat/lng (use `python-geohash` or compute inline).
- Store `geohash` attribute; GSI with `geohash_prefix` (length 5 ≈ 5 km) as partition key.
- Query: `KeyConditionExpression="geohash_prefix = :gh"`, then filter by exact distance in Python.

### RBAC
- Cognito groups: `Hospital`, `Donor`, `Courier`, `Doctor`.
- API Gateway HTTP API JWT authorizer verifies the token.
- FastAPI dependency re-reads `cognito:groups` claim and enforces per-route.

### Tracing
- `aws-xray-sdk` patches boto3 + httpx automatically.
- Every Lambda has `Tracing: Active`.
- One README screenshot of a cross-service trace is a Phase-1 deliverable.

---

## 9. Definition of Done — Per PR

A PR is mergeable only if:
- [ ] `pytest` passes for affected services.
- [ ] `ruff check` and `ruff format --check` pass.
- [ ] `terraform fmt -check` and `terraform validate` pass.
- [ ] No new AWS resource outside the banned-services list (§2.1).
- [ ] No new IAM `*` action without a justification comment.
- [ ] If a new env var is added, `.env.example` updated.
- [ ] If a new event type is added, Pydantic schema added in `packages/shared/`.

---

## 10. MCP Servers (the agent's eyes into AWS)

Configured in `.claude/settings.json` (separate deliverable). The agent has read-mostly access to AWS via:

| MCP | What the agent does with it |
|---|---|
| `aws-api-mcp-server` | Inspect any AWS resource via scoped IAM role |
| `cost-explorer-mcp-server` | Verify spend before/after changes; warn user proactively |
| `cloudwatch-logs-mcp-server` | Pull Lambda logs when debugging |
| `dynamodb-mcp-server` | Inspect tables, run queries during dev |
| GitHub MCP | PR status, CI runs, issues |
| Context7 / Ref | Live AWS SDK + FastAPI docs |

**IAM scope for the MCP user:** read-only on most services, write only on resources tagged `Project=MediSync`. Production writes still go through Terraform + GitHub Actions — the MCP user cannot deploy.

---

## 11. Cost Discipline (repeat from rules; this matters)

- **Before adding any AWS resource**, the agent should mentally check: "Is this in §4? Is it free-tier? Is it in the banned list?"
- **When in doubt about cost**, call the Cost Explorer MCP and report the current month's spend to the user before applying.
- **Suspicious signs to flag:** any resource with "instance," "cluster," "node," or "endpoint" in the type. Most of those are not free.

---

## 12. Pointers to Other Files

- **`spec.md`** — original tech spec. Sections §2, §3, §4, §6, §7 still apply conceptually; vendor choices are overridden by §4 of this file.
- **`Requirement.md`** — vision and "why." Use the framing language for the README.
- **`use_case.md`** — the "Golden Hour" narrative. Use this verbatim for interview prep and the README story.
- **`C:\Users\Admin\.claude\plans\i-need-you-to-sorted-pearl.md`** — the approved build plan with milestones M0–M5.

---

## 13. When the Agent Is Unsure

Stop and ask the user. Specifically ask before:
- Creating an AWS account or making the first real AWS API call.
- Provisioning anything outside the §4 list.
- Adding a new third-party paid service.
- Modifying IAM policies that touch billing, account, or org settings.
- Running `terraform apply` against `prod`.

Local file edits, scaffolding, writing FastAPI handlers, writing tests, editing Terraform without applying — proceed without asking.
