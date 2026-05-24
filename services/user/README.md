# MediSync — User Service

Azure Functions (Python 3.12, **v2 programming model**) app that owns **user
profiles** for Hospitals, Donors, Couriers and Doctors. Profiles are stored in
the Cosmos DB `profiles` container; data-plane access uses
`DefaultAzureCredential` (Managed Identity in Azure, `az login` locally) — no
keys or connection strings in code or config.

## Endpoints

Functions adds the default `/api` route prefix.

| Method  | Route                  | Purpose                                          |
| ------- | ---------------------- | ------------------------------------------------ |
| `GET`   | `/api/health`          | Liveness probe (no Cosmos call).                 |
| `POST`  | `/api/auth/signup`     | Register a Hospital / Donor / Courier / Doctor.  |
| `GET`   | `/api/users/{user_id}` | Fetch one profile by id.                         |
| `PATCH` | `/api/users/{user_id}` | Partial update (e.g. a Donor toggling availability). Optimistic-locked via Cosmos ETag → `409` on a concurrent write. |

## Layout

```
services/user/
├── function_app.py            ← v2 entry point; registers the routes blueprint
├── host.json                  ← Functions host config + extension bundle
├── local.settings.example.json← template for local.settings.json (gitignored)
├── pyproject.toml             ← uv-managed deps + ruff/pytest config
├── requirements.txt           ← runtime deps for the Functions Oryx build
├── app/
│   ├── config.py              ← env-var settings (COSMOS_*, App Insights)
│   ├── models.py              ← Pydantic v2 schemas (Profile, SignupRequest, …)
│   ├── repository.py          ← Cosmos data access (ETag optimistic locking)
│   ├── routes.py              ← HTTP handlers (func.Blueprint)
│   └── telemetry.py           ← optional Application Insights / OpenTelemetry
└── tests/
    └── test_models.py         ← schema unit tests (no Azure needed)
```

## Local development

```powershell
# from services/user/
uv sync                                  # create .venv, install deps + dev tools
Copy-Item local.settings.example.json local.settings.json   # then edit values
uv run func start                        # runs the Function host on :7071
```

`local.settings.json` is gitignored. `COSMOS_ENDPOINT` points at the dev Cosmos
account — your `az login` identity needs the **Cosmos DB Built-in Data
Contributor** data-plane role on it (granted via Terraform, not yet wired).

## Quality gates (context.md §9)

```powershell
uv run pytest            # unit tests
uv run ruff check .      # lint
uv run ruff format .     # format
```

After changing dependencies, regenerate the deployment manifest:

```powershell
uv pip compile pyproject.toml -o requirements.txt
```

## Not yet wired (deliberate)

- **Authentication.** HTTP auth level is `ANONYMOUS`; real authorization is
  Entra External ID JWT validation (context.md §8), pending the Entra tenant
  runbook. See the `TODO(entra)` in `app/routes.py`.
- **Infrastructure.** The Function App, its Storage Account, the Managed
  Identity, the `profiles` Cosmos container and its RBAC role assignment are
  not in `infra/` yet — `infra/functions.tf` and `infra/identity.tf` are still
  placeholders. Deployment happens once that Terraform lands.
