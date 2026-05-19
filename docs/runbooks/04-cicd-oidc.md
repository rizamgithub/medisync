# Runbook 04 — GitHub Actions → Azure via OIDC (federated credentials)

> **Purpose:** Prove end-to-end that GitHub Actions can authenticate to Azure as the `medisync-deploy` service principal **without storing any secret in GitHub**, using OIDC federated credentials.
>
> By the end you'll have:
> 1. Three repository-level **identifiers** (not secrets) configured in GitHub: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
> 2. A workflow file `.github/workflows/azure-auth-probe.yml` that runs on push to `main` and on manual dispatch.
> 3. A successful workflow run where `az group show rg-medisync-prod` returns JSON proving the OIDC handshake worked.
>
> **Estimated time:** 20–30 minutes.
> **Prerequisite:** Runbooks 01 + 02 + 03 complete. Repo exists at `github.com/rizamgithub/medisync`. Federated credential on `medisync-deploy` is configured for `Branch = main`.

---

## Concepts (read once)

- **Why no secret?** A client secret is a long-lived bearer token: leak it, anyone can act as the SP until you rotate. OIDC federated credentials instead let GitHub mint a **short-lived ID token (≈15 min)** per workflow run, signed by GitHub's OIDC issuer (`token.actions.githubusercontent.com`). Azure validates the token's `iss`, `sub`, and `aud` claims against the federated credential you registered on the SP, and exchanges it for an Azure access token. Nothing long-lived crosses the wire.
- **The three "secrets" in GitHub are not secrets.** `AZURE_CLIENT_ID` etc. are just GUIDs that identify *which* SP to log into. You could put them in the workflow YAML in plaintext and it would still work — Azure refuses the login unless the OIDC token's `sub` matches the federated credential. The convention is to keep them as repo secrets anyway so the YAML is portable across forks/environments.
- **The `sub` claim** sent by GitHub depends on what triggered the workflow:
  - Push to a branch: `repo:<org>/<repo>:ref:refs/heads/<branch>` → e.g. `repo:rizamgithub/medisync:ref:refs/heads/main`
  - Pull request: `repo:<org>/<repo>:pull_request`
  - Environment deploy: `repo:<org>/<repo>:environment:<env>`
  - Tag push: `repo:<org>/<repo>:ref:refs/tags/<tag>`
  Your federated credential must match one of these patterns exactly. We registered the **Branch = main** flavour in runbook 02, so this workflow must trigger via push/dispatch on `main`.
- **`permissions:` block on the job** is what tells GitHub to issue the OIDC token. Without `id-token: write`, the `azure/login@v2` action will fail with a confusing 403.

---

## Step 1 — Add the three repo identifiers in GitHub

1. Open https://github.com/rizamgithub/medisync in a browser.
2. **Settings** (top tab) → left sidebar **Secrets and variables** → **Actions**.
3. Click **New repository secret** and add each of the three below. Get the values from `.temp/azureid.md`:

| Name | Value source in `.temp/azureid.md` |
|---|---|
| `AZURE_CLIENT_ID` | `medisync-deploy` → `Application (client) ID` |
| `AZURE_TENANT_ID` | Microsoft Entra ID → `Tenant ID` |
| `AZURE_SUBSCRIPTION_ID` | Subscription → `Subscription ID` |

> ⚠️ **Do NOT** add `AZURE_CLIENT_SECRET`. That belongs to `medisync-admin` (local CLI) and has no business in CI. Adding it would defeat the entire point of OIDC.

After saving, you should see exactly three secrets listed (values masked as `***`).

---

## Step 2 — Create the workflow file locally

In the repo root, create `.github/workflows/azure-auth-probe.yml` with the contents below.

```yaml
name: azure-auth-probe

on:
  push:
    branches: [main]
    paths:
      - '.github/workflows/azure-auth-probe.yml'
  workflow_dispatch: {}

permissions:
  id-token: write      # required: lets GitHub mint the OIDC token
  contents: read       # required: lets actions/checkout read the repo

jobs:
  probe:
    name: Prove OIDC handshake to Azure
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Azure login via OIDC (no secret)
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Show the resource group we're allowed to touch
        run: |
          az account show -o table
          echo "---"
          az group show --name rg-medisync-prod -o table
          echo "---"
          az group show --name rg-medisync-prod --query 'id' -o tsv
```

Notes on the YAML:
- `paths:` restricts the push trigger to only fire when this workflow file itself changes — so we don't burn CI minutes on every commit while we're still scaffolding. Remove it later when we add real deploy logic.
- `workflow_dispatch: {}` adds a **"Run workflow"** button in the Actions tab so you can re-run on demand without pushing.
- The probe **does not** run `terraform apply` or create anything. It only *reads* the RG to confirm the auth chain works. Cost = $0.

---

## Step 3 — Commit and push

```powershell
git checkout -b cicd-oidc-probe
git add .github/workflows/azure-auth-probe.yml docs/runbooks/04-cicd-oidc.md
git commit -m "ci: add OIDC auth probe workflow + runbook 04"
git push -u origin cicd-oidc-probe
```

> **Why a branch, not `main` directly?** Lets you open a PR and inspect the workflow file in GitHub's UI before it runs. If you'd rather push straight to `main`, that also works — the workflow will trigger on push.

Then either:
- Open a PR and merge it (workflow fires on push to `main` after merge), **or**
- Use the **workflow_dispatch** path: go to **Actions** → **azure-auth-probe** (it will appear in the sidebar once the YAML lands on `main`) → **Run workflow** → pick branch `main` → **Run workflow** button.

For the *very first run*, simplest is: merge to `main`, then **Actions → azure-auth-probe → Run workflow** to trigger it manually rather than waiting for the path filter.

---

## Step 4 — Watch the run

1. Go to **Actions** tab in the repo.
2. Click the most recent **azure-auth-probe** run.
3. Click the **probe** job → expand each step.

Expected outcome:

- ✅ **Checkout** — green tick.
- ✅ **Azure login via OIDC** — last log line should be `Login successful.`
- ✅ **Show the resource group** — `az account show` prints your subscription, `az group show` prints the `rg-medisync-prod` row with location `southeastasia`, and the final `tsv` query prints the full RG resource ID.

If all three steps are green, **OIDC end-to-end works**. The `medisync-deploy` SP can act on `rg-medisync-prod` from CI with no stored credentials.

---

## Step 5 — Final state checklist

- [ ] Three repo secrets configured (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`) — no `AZURE_CLIENT_SECRET`.
- [ ] `.github/workflows/azure-auth-probe.yml` exists on `main`.
- [ ] At least one green run in the Actions tab showing `Login successful.` and the RG details.
- [ ] No new role assignments created on the SP — it still has only `Contributor` on `rg-medisync-prod`.

---

## What's next

Runbook **`05-terraform-scaffold.md`** — structure the real `infra/` Terraform layout (`identity.tf`, `cosmos.tf`, `functions.tf`, `monitoring.tf` as modules) without provisioning anything yet. Then runbook 06 will wire this same OIDC workflow to run `terraform plan` on PRs and `terraform apply` on merges to `main`.

---

## Troubleshooting

### `AADSTS700016: Application with identifier '...' was not found in the directory`
The `AZURE_CLIENT_ID` repo secret has the wrong GUID. It must be the **Application (client) ID** of `medisync-deploy`, not its Object ID and not the `medisync-admin` client ID. Re-check `.temp/azureid.md`.

### `AADSTS70021: No matching federated identity record found for presented assertion`
The OIDC token's `sub` claim doesn't match the federated credential you set up. Check at https://portal.azure.com → **Entra ID → App registrations → medisync-deploy → Certificates & secrets → Federated credentials**:
- **Organization** must be `rizamgithub` (case-sensitive — GitHub usernames are case-insensitive for login but the OIDC subject is **case-sensitive**).
- **Repository** must be `medisync`.
- **Entity type** = Branch, **Branch** = `main`.
- If you triggered the workflow from a branch *other than* main (e.g. `cicd-oidc-probe`), the `sub` will be `...:ref:refs/heads/cicd-oidc-probe` and won't match. **Run the workflow from `main`** — either merge first, or temporarily add a second federated credential for your test branch.

### `Error: Login failed with Error: Az CLI Login failed.`
Almost always the `permissions:` block is missing `id-token: write`. Re-check Step 2 — that block must be at the job level (or workflow level), not absent.

### Workflow doesn't appear in the Actions tab
The YAML hasn't landed on the **default branch** yet, or the file is in the wrong path. It must be `.github/workflows/*.yml` exactly (note the leading dot). Verify in GitHub's file browser that the file is at that path on `main`.

### `az group show` returns 403 / AuthorizationFailed
The OIDC login succeeded but the SP doesn't have a role assignment on `rg-medisync-prod`. Repeat runbook 02 Step 8 (Contributor on the RG).

### Subscription not visible after login
`azure/login@v2` defaults to the subscription you passed. If you ever need to switch in CI: `az account set --subscription ${{ secrets.AZURE_SUBSCRIPTION_ID }}`. For our setup the default works.
