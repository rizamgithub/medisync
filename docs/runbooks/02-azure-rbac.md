# Runbook 02 — Azure RBAC & Service Principals

> **Purpose:** Stop using the Global Admin account for daily work. Create two **service principals (SPs)** with **least-privilege RBAC** scoped to `rg-medisync-prod`:
>
> 1. `medisync-admin` — for **local CLI / Terraform** from your laptop. Authenticates with a client secret. Bypasses interactive MFA (important since Microsoft's tenant-wide MFA enforcement for CLI / SDKs is active as of Oct 2025).
> 2. `medisync-deploy` — for **GitHub Actions CI/CD**. Authenticates via **OIDC federated credentials** — no secrets stored in GitHub.
>
> **Estimated time:** 30–45 minutes.
> **Prerequisite:** Runbook 01 complete. Subscription ID, tenant ID, and `rg-medisync-prod` exist.

---

## Why two service principals (and not just one)

Different blast radii:

| Identity | Used by | Auth | Secret lifetime |
|---|---|---|---|
| `medisync-admin` | You at the terminal | Client secret | 6 months, rotate manually |
| `medisync-deploy` | GitHub Actions | OIDC federated credential | No secret — short-lived token per run |

If the laptop secret leaks, the deploy pipeline is unaffected. If the GitHub repo is compromised, the federated credential only works from that specific repo + branch + workflow — useless elsewhere.

Both are scoped to `rg-medisync-prod` only. Neither can touch the subscription, the tenant, or other resource groups.

---

## Concepts (read once, then skip)

- **App registration** = the *definition* of an application identity in Entra ID (think: class).
- **Service principal** = the *instance* of that app inside this specific tenant (think: object). Azure creates it automatically when you create the app registration. RBAC role assignments target the SP, not the app.
- **Client ID** (a.k.a. Application ID) = public GUID identifying the app. Safe to commit.
- **Object ID** = the SP's unique ID inside this tenant. Used when assigning roles.
- **Tenant ID** = your Entra directory's GUID. From runbook 01.
- **Client secret** = password for the app. Treat like a credit card number.
- **Federated credential** = a trust relationship that lets an external identity provider (GitHub) request short-lived tokens for this SP. No long-lived secret.

---

## Step 1 — Create `medisync-admin` app registration

1. Azure Portal → top search → **Microsoft Entra ID** → click result.
2. Left sidebar → **App registrations** → **+ New registration**.
3. **Name:** `medisync-admin`
4. **Supported account types:** **Single tenant only - default directory** (Microsoft also labels this "Accounts in this organizational directory only" in some regions — same option, top of the list).
5. **Redirect URI:** leave blank.
6. Click **Register**.
7. You land on the app's Overview page. **Copy and save** into `.temp/azureid.md` under a new `## medisync-admin` section:
   - **Application (client) ID:** `<GUID>`
   - **Directory (tenant) ID:** `<GUID>` (should match runbook 01)
   - **Object ID:** `<GUID>` (the *app's* object ID — different from the SP object ID we need below)

---

## Step 2 — Get the service principal's Object ID

The SP was auto-created when you registered the app, but its Object ID is *not* shown on the App Registration page. You need it for the role assignment in Step 4.

1. Still in **Microsoft Entra ID** → left sidebar → **Enterprise applications**.
2. Top filter: change **Application type** = **All Applications** (default hides yours). Click **Apply**.
3. Search `medisync-admin` → click it.
4. **Copy and save** into `.temp/azureid.md`:
   - **Object ID** of the enterprise app (this *is* the SP Object ID — different from Step 1's Object ID).

> If you skip this and use the wrong Object ID in role assignment, the CLI command silently picks the wrong identity. Be deliberate here.

---

## Step 3 — Create a client secret for `medisync-admin`

1. Back to **App registrations** → click `medisync-admin`.
2. Left sidebar → **Certificates & secrets** → **Client secrets** tab → **+ New client secret**.
3. **Description:** `local-cli-2026-05`
4. **Expires:** **180 days** (6 months — Azure caps at 24 months; shorter is safer).
5. Click **Add**.
6. **IMMEDIATELY copy the `Value` column** into `.temp/azureid.md`. It will never be shown again after you leave this page.
   - Format: `~xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Also note: secret **ID** (less sensitive, used for deletion later).
7. Add a calendar reminder for **2026-11-15** to rotate this secret (180 days from today, minus 4-day buffer).

---

## Step 4 — Assign `medisync-admin` the Contributor role on `rg-medisync-prod`

This is the actual RBAC grant. Until this step, the SP exists but can do nothing.

1. Top search → **Resource groups** → click → click **`rg-medisync-prod`**.
2. Left sidebar → **Access control (IAM)** → **+ Add** → **Add role assignment**.
3. **Role tab:** scroll or search → select **Contributor** → click **Next**.

   > Why not Owner? Owner can grant roles to other identities — escalation risk. Contributor can create/delete every resource but cannot hand out permissions. Right level for daily work.

4. **Members tab:**
   - **Assign access to:** **User, group, or service principal** (this option also covers SPs — Microsoft's UI is misleading).
   - Click **+ Select members** → in the panel, search `medisync-admin` → click the result → **Select**.
5. Click **Review + assign** → **Review + assign** again.
6. Confirm the new row appears in the IAM list with **Role = Contributor**, **Scope = This resource**.

---

## Step 5 — Test `medisync-admin` login from your laptop

You'll need Azure CLI installed first. If `az --version` errors, install it:

```powershell
winget install -e --id Microsoft.AzureCLI
```

Close and reopen PowerShell after install, then:

```powershell
az login --service-principal `
  --username <medisync-admin-client-id> `
  --password <client-secret-value> `
  --tenant <tenant-id>
```

Expected output: JSON array showing one subscription (`Azure subscription 1`) and `"state": "Enabled"`.

Then verify scoped access works:

```powershell
az group show --name rg-medisync-prod
```

Should print the RG's JSON. Now verify the scope blocks broader access:

```powershell
az account list-locations --output table
```

This **should** succeed (read-only metadata, allowed for any authenticated SP).

```powershell
az group list --output table
```

This should show **only** `rg-medisync-prod` (or possibly empty if listing requires subscription-level read — that's expected and confirms the scope is tight). The SP cannot enumerate other RGs because it has no role at the subscription level. ✅

Sign out when done:

```powershell
az logout
```

---

## Step 6 — Create `medisync-deploy` app registration (for GitHub Actions)

Same as Step 1, different name.

1. **Microsoft Entra ID** → **App registrations** → **+ New registration**.
2. **Name:** `medisync-deploy`
3. **Supported account types:** **Single tenant**.
4. **Redirect URI:** blank.
5. **Register**.
6. Save **Application (client) ID** to `.temp/azureid.md` under `## medisync-deploy`.
7. Repeat Step 2 (Enterprise applications) to capture the SP **Object ID** for this app too.

---

## Step 7 — Add a federated credential for GitHub Actions

This is the magic that lets GitHub Actions get a short-lived Azure token without storing any secret.

1. **App registrations** → click `medisync-deploy`.
2. Left sidebar → **Certificates & secrets** → **Federated credentials** tab → **+ Add credential**.
3. **Federated credential scenario:** **GitHub Actions deploying Azure resources**.
4. Fill in:
   - **Organization:** `rizamgithub` (your GitHub username — case-sensitive).
   - **Repository:** `medisync` (matches https://github.com/rizamgithub/medisync).
   - **Entity type:** **Branch**.
   - **GitHub branch name:** `main`.
   - **Name:** `github-main-branch` (internal label).
5. Click **Add**.

> **Future you:** add a second federated credential with Entity type = **Pull request** if you want PR-triggered preview deployments. And one with Entity type = **Environment** = `production` for protected deploys.

---

## Step 8 — Assign `medisync-deploy` Contributor on `rg-medisync-prod`

Identical to Step 4 but for `medisync-deploy`.

1. **Resource groups** → `rg-medisync-prod` → **Access control (IAM)** → **+ Add** → **Add role assignment**.
2. Role = **Contributor** → Next.
3. Members → **User, group, or service principal** → **+ Select members** → search `medisync-deploy` → Select.
4. **Review + assign** → confirm.

You should now see **two** custom role assignments on the RG: `medisync-admin` (Contributor) and `medisync-deploy` (Contributor).

---

## Step 9 — Document the GitHub Actions side (do later, when repo exists)

When you set up the GitHub repo, you'll add these **repository secrets** (not secret *values* — just identifiers):

| Repo secret name | Source |
|---|---|
| `AZURE_CLIENT_ID` | `medisync-deploy` Application (client) ID |
| `AZURE_TENANT_ID` | Tenant ID from runbook 01 |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID from runbook 01 |

And your workflow uses `azure/login@v2` with `client-id` / `tenant-id` / `subscription-id` (no `client-secret`). The `permissions: id-token: write` block on the job is what triggers GitHub to mint the OIDC token Azure validates against the federated credential.

We'll cement this in runbook 04 (CI/CD) once the repo is git-initialized.

---

## Step 10 — Final state checklist

- [ ] `medisync-admin` app registration exists with one active client secret (180-day expiry, rotation reminder set).
- [ ] `medisync-deploy` app registration exists with one federated credential for `main` branch.
- [ ] Both SPs have **Contributor** on `rg-medisync-prod` and **no other role assignments** anywhere.
- [ ] `.temp/azureid.md` contains: both client IDs, both SP Object IDs, the `medisync-admin` client secret.
- [ ] You've signed in once with `medisync-admin` via `az login --service-principal` and confirmed it works.

---

## What's next

Runbook **`03-az-cli-and-tooling.md`** — install Azure CLI + Azure Functions Core Tools, configure CLI default subscription, and validate Terraform's `azurerm` provider can authenticate as `medisync-admin`.

---

## Troubleshooting

### "Insufficient privileges to complete the operation" when creating the app registration
Your account isn't Global Admin / Application Administrator in this tenant. Runbook 01's signup account should be Global Admin — sign out and back in if you switched accounts.

### Can't find the SP in "Add role assignment" search
Wait 30–60 seconds after creating the app registration — Entra needs to replicate the SP object across the directory. Refresh the IAM page and search again.

### `az login --service-principal` returns "Invalid client secret provided"
- You copied the secret **ID** instead of the **Value**. The Value starts with `~` or similar and is only shown once.
- Secret expired — check **Certificates & secrets** for the expiry date.

### GitHub Actions: `AADSTS70021: No matching federated identity record found`
The OIDC token's `sub` claim doesn't match what you configured. Check that:
- Organization name in federated credential matches your GitHub login *exactly* (case-sensitive).
- Repository name matches.
- Branch name in the credential matches the branch the workflow is running from.

### Rotating the `medisync-admin` client secret
1. **Certificates & secrets** → **+ New client secret** → create the new one *before* deleting the old.
2. Update your local config / password manager with the new value.
3. Run `az login --service-principal` with the new secret to confirm it works.
4. Delete the old secret row.
