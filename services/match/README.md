# MediSync — Match Service

Azure Functions (Python 3.12, **v2 programming model**) app that owns the
**emergency matching Saga**. It is the event-driven centrepiece of MediSync:
a **Durable Functions** orchestrator coordinates finding, reserving, notifying
and completing a match — and compensates if any step fails.

## Flow

```
POST /api/request/emergency
        │  persist MatchRecord (status=Pending)
        │  publish  MediSync.EmergencyRequestCreated  ──► Event Grid topic
        ▼
on_emergency_request  (Event Grid trigger + durable client)
        │  start_new
        ▼
match_orchestrator  (Durable Functions Saga)
        ├─ find_inventory       → inventory service GET /api/inventory
        ├─ reserve_inventory    → inventory service POST /api/inventory/{id}/reserve
        ├─ notify_parties       → publish MediSync.MatchFound  (+ TODO: ACS email)
        └─ complete_match       → MatchRecord status=Matched
        │
        └─ on failure (compensation):
             release_reservation → publish MediSync.ReservationReleased
             complete_match      → MatchRecord status=Failed, publish MediSync.MatchFailed
```

The orchestrator is deterministic and does no I/O — every side effect is an
activity function (context.md §8).

## Endpoints

| Method | Route                          | Purpose                                         |
| ------ | ------------------------------ | ----------------------------------------------- |
| `GET`  | `/api/health`                  | Liveness probe.                                 |
| `POST` | `/api/request/emergency`       | Submit an emergency request → `202 Accepted`; publishes the trigger event. |
| `GET`  | `/api/request/{request_id}`    | Poll a request and its current Saga outcome.    |

## Event contracts (context.md §6)

Namespaced, PascalCase, past-tense. Pydantic-typed in `app/events.py`:
`MediSync.EmergencyRequestCreated` · `MediSync.MatchFound` ·
`MediSync.MatchFailed` · `MediSync.ReservationReleased`.

## Layout

```
services/match/
├── function_app.py            ← df.DFApp entry point; registers both blueprints
├── host.json                  ← + durableTask hub config
├── .funcignore · local.settings.example.json · pyproject.toml · requirements.txt
├── app/
│   ├── config.py              ← env-var settings
│   ├── models.py              ← EmergencyRequestCreate, MatchRecord, enums
│   ├── matching.py            ← blood-type compatibility + unit selection (pure)
│   ├── events.py              ← Event Grid event contracts (Pydantic)
│   ├── publisher.py           ← Event Grid publisher (DefaultAzureCredential)
│   ├── inventory_client.py    ← HTTP client → inventory service
│   ├── repository.py          ← Cosmos `requests` container access
│   ├── routes.py              ← HTTP blueprint (submit / status)
│   ├── saga.py                ← Durable blueprint (starter + orchestrator + 5 activities)
│   └── telemetry.py           ← optional Application Insights / OpenTelemetry
└── tests/
    ├── test_matching.py       ← blood compatibility + selection
    ├── test_models.py         ← request/record schemas
    └── test_events.py         ← event contracts
```

## Local development

```powershell
# from services/match/
uv sync
Copy-Item local.settings.example.json local.settings.json   # then edit values
uv run func start                        # Durable host on :7071
```

`local.settings.json` is gitignored. Durable Functions needs a storage
account for its task hub — `AzureWebJobsStorage` points at Azurite locally.

## Quality gates (context.md §9)

```powershell
uv run pytest            # unit tests
uv run ruff check .      # lint
uv run ruff format .     # format
```

## Not yet wired (deliberate)

- **Authentication.** HTTP auth level is `ANONYMOUS`; real authorization is
  Entra External ID JWT validation (context.md §8), pending the Entra runbook.
- **Email.** `notify_parties` has a `TODO(acs-email)` — Azure Communication
  Services Email needs a verified domain (future runbook).
- **Compensation completeness.** `release_reservation` publishes
  `ReservationReleased`; the inventory service still needs a subscriber that
  flips the unit back to `Available`.
- **Shared event package.** `app/events.py` should move to `packages/shared/`
  once another service produces/consumes events (context.md §5, §9).
- **Infrastructure.** Function App, Storage account, Managed Identity, the
  Event Grid topic + subscription, and the `requests` Cosmos container are not
  in `infra/` yet.
