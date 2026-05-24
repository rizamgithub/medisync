# `medisync_shared` — shared package

Cross-service domain types and **Event Grid event contracts** (context.md
§5, §9). One definition of each event schema, consumed by every service that
produces or reacts to MediSync domain events.

| Module | Contents |
| ------ | -------- |
| `domain.py` | `BloodType`, `Urgency`, `GeoLocation` — value types used inside event payloads. |
| `events.py` | `EventType`, `EVENT_DATA_VERSION`, and the Pydantic `*Data` payload schemas. |

## Why it is *vendored*, not pip-installed

Azure Functions deploys **one folder per app**, and its Oryx remote build only
`pip install`s that app's `requirements.txt` — it cannot see a sibling
`packages/` folder. So this package is **copied as source** into each service
that needs it, by `scripts/sync-shared.ps1`:

```
packages/shared/medisync_shared/   ← source of truth (committed)
        │  scripts/sync-shared.ps1
        ▼
services/match/medisync_shared/      ← copy (gitignored)
services/inventory/medisync_shared/  ← copy (gitignored)
```

The copies are listed in `.gitignore` (`services/*/medisync_shared/`) so the
schema is never duplicated in version control.

## When to run the sync script

Run `pwsh scripts/sync-shared.ps1` whenever the copies could be stale:

- after **cloning** the repo, before `uv run pytest` or `func start`;
- after **editing** anything under `packages/shared/`;
- immediately before `func azure functionapp publish` (runbook 09, Step 4).

At runtime the copy sits at the Function App root, so it imports as a normal
top-level package: `from medisync_shared.events import EventType`.

The only third-party dependency is `pydantic`, which every service already
declares — nothing extra goes into a service `requirements.txt`.
