# MediSync — Inventory Service

Azure Functions (Python 3.12, **v2 programming model**) app that owns
**blood/organ stock units**: geohash-bucketed region search, the ETag-guarded
*reserve* transition consumed by the match service's Saga, and an Event Grid
**compensation handler** that releases a reservation back to `Available`.
Stock lives in the Cosmos DB `inventory` container; data-plane access uses
`DefaultAzureCredential` (Managed Identity in Azure, `az login` locally).

## Endpoints

Functions adds the default `/api` route prefix.

| Method | Route                              | Purpose                                                  |
| ------ | ---------------------------------- | -------------------------------------------------------- |
| `GET`  | `/api/health`                      | Liveness probe (no Cosmos call).                         |
| `POST` | `/api/inventory`                   | Register a unit of stock; geohash computed from location.|
| `GET`  | `/api/inventory`                   | Region search — `?lat=&lng=&radius_km=&sub_type=`.       |
| `POST` | `/api/inventory/{item_id}/reserve` | Reserve a unit (`Available → Reserved`), ETag-locked → `409` on a concurrent claim or a non-available item. |

## Event handling (context.md §6, §8)

`on_reservation_released` is an **Event Grid trigger** — not an HTTP route. It
subscribes to `MediSync.ReservationReleased` (published by the match service's
Saga when it rolls back a reservation) and flips the affected unit
`Reserved → Available`, closing the Saga's compensation loop.

Event Grid delivers **at-least-once**, so the handler is **idempotent**: a unit
already `Available`, or reserved by a different request, is left untouched. The
event carries the unit's `geohash_prefix` (its partition key) so the handler
does a single-partition point read rather than a cross-partition scan. The
event schema is the shared `medisync_shared.events.ReservationReleasedData`.

## Geo design (context.md §8)

- On write, `geo.encode()` produces a 9-char **geohash** from lat/lng; the
  first 5 chars (`geohash_prefix`, a ~4.9 km cell) are the Cosmos **partition
  key**.
- A region query reads exactly one partition
  (`WHERE c.geohash_prefix = @gh`), then filters by exact **haversine**
  distance in Python and sorts by `distance_km`.
- Known limitation: only the single prefix cell is queried — a point near a
  cell boundary can miss stock in an adjacent cell. Neighbour-cell expansion
  is a documented refinement, deferred for the scaffold (see `repository.py`).

## Layout

```
services/inventory/
├── function_app.py            ← v2 entry point; registers HTTP + subscriber blueprints
├── host.json · .funcignore · local.settings.example.json
├── pyproject.toml · requirements.txt
├── medisync_shared/           ← vendored shared package (gitignored — sync-shared.ps1)
├── app/
│   ├── config.py              ← env-var settings (COSMOS_INVENTORY_*)
│   ├── geo.py                 ← geohash encode + haversine (no deps)
│   ├── models.py              ← Pydantic v2 schemas
│   ├── repository.py          ← Cosmos access (region query + ETag reserve/release)
│   ├── routes.py              ← HTTP handlers (func.Blueprint)
│   ├── subscriber.py          ← Event Grid handler — ReservationReleased compensation
│   └── telemetry.py           ← optional Application Insights / OpenTelemetry
└── tests/
    ├── test_geo.py            ← geohash + haversine vs known reference values
    └── test_models.py         ← schema unit tests
```

## Local development

```powershell
pwsh ..\..\scripts\sync-shared.ps1       # vendor medisync_shared (first run / after edits)
# from services/inventory/
uv sync
Copy-Item local.settings.example.json local.settings.json   # then edit values
uv run func start                        # runs the Function host on :7071
```

`local.settings.json` is gitignored. Your `az login` identity needs the
**Cosmos DB Built-in Data Contributor** data-plane role on the dev account.

## Quality gates (context.md §9)

```powershell
uv run pytest            # unit tests
uv run ruff check .      # lint
uv run ruff format .     # format
```

## Not yet wired (deliberate)

- **Authentication.** HTTP auth level is `ANONYMOUS`; real authorization is
  Entra External ID JWT validation (context.md §8), pending the Entra tenant
  runbook.
- **Deployment.** The Function App, Storage Account, Managed Identity, the
  `inventory` Cosmos container and the `ReservationReleased` Event Grid
  subscription are all written in `infra/` but **not yet applied** — that
  happens when the user executes runbook 09.
