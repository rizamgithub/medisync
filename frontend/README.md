# MediSync — Frontend

Next.js (App Router, TypeScript) UI for MediSync. It is a **static export** —
a set of client-rendered pages that call the Function App APIs directly — and
is hosted on **Azure Static Web Apps** (Free tier, context.md §3).

## Pages

| Route        | Purpose                                                            |
| ------------ | ------------------------------------------------------------------ |
| `/`          | Dashboard — what the system does and how a request flows.          |
| `/request`   | Submit an emergency request (calls the match service).             |
| `/status`    | Live Saga outcome for a request — `/status?id=<request_id>`, polls. |
| `/inventory` | Search Available stock by region, and register new stock.          |

## Layout

```
frontend/
├── next.config.mjs            ← output: "export" (static)
├── staticwebapp.config.json   ← Azure Static Web Apps config
├── .env.example               ← NEXT_PUBLIC_* API base URLs
└── src/
    ├── app/
    │   ├── layout.tsx · globals.css
    │   ├── page.tsx           ← dashboard
    │   ├── request/page.tsx
    │   ├── status/page.tsx
    │   └── inventory/page.tsx
    ├── components/            ← Nav, StatusBadge
    └── lib/
        ├── types.ts           ← TS mirror of the backend Pydantic schemas
        ├── api.ts             ← typed fetch client for the Function Apps
        └── auth.ts            ← MSAL/Entra auth — stubbed (see below)
```

## Local development

```powershell
# from frontend/
pnpm install
Copy-Item .env.example .env.local   # point at local `func start` ports
pnpm dev                            # http://localhost:3000
```

The pages call the match and inventory Function Apps — run those with
`func start` (or set `.env.local` at the deployed Function App URLs).

## Build & deploy

```powershell
pnpm build        # type-checks, lints, and writes the static site to ./out
```

`pnpm build` produces `out/` — deploy that to Azure Static Web Apps. Set the
`NEXT_PUBLIC_*` variables (see `.env.example`) **before** building; they are
inlined into the export. Provisioning the Static Web App in Terraform is a
follow-up task — it is not in `infra/` yet.

## Not yet wired (deliberate)

- **Authentication.** `src/lib/auth.ts` is a stub returning a fixed demo
  operator. Real MSAL.js + Entra External ID sign-in (context.md §3, §8) is
  blocked on the Entra External ID tenant — see the `TODO(entra)` there.
- **Infrastructure.** No `azurerm_static_web_app` in `infra/` yet.
