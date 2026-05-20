# Runbook 07 — Remote Terraform state on Azure Blob

> **Purpose:** Move Terraform state off your laptop into an Azure Storage container, so state is durable, lockable, and reachable by CI.
>
> By the end you'll have:
> 1. A bootstrapped Storage account + `tfstate` container (the one resource *not* managed by Terraform — on purpose).
> 2. `infra/backend.tf` switched from local to the `azurerm` backend, authenticating via Azure AD (no storage keys).
> 3. Your existing 6-resource state migrated into the blob, with `terraform plan` still reporting **no changes**.
>
> **Estimated time:** 20–30 minutes.
> **Prerequisite:** Runbook 06 complete. Cosmos DB live, state currently local at `infra/terraform.tfstate`.
> **Cost:** ~**$0/month**. A `Standard_LRS` account holding a few-KB state file is fractions of a cent in storage; transactions are negligible.

---

## Concepts (read once)

### Why move state off the laptop
Terraform's *state file* is its record of what it has created and how that maps to your `.tf` code. Right now it's a single file on your disk. Three problems that remote state fixes:
- **Durability** — lose the laptop, lose the only record of your deployed infrastructure.
- **Collaboration / CI** — GitHub Actions can't see a file on your machine. CI *must* read and write shared state.
- **Locking** — if two `terraform apply` runs overlap, they can corrupt state. The `azurerm` backend takes a **blob lease** on the state file for the duration of each run — an automatic mutex. (This is why we don't need a separate lock table the way AWS S3 + DynamoDB does.)

### The chicken-and-egg exception
`context.md` rule 3 says *everything* is Terraform-managed. The state Storage account is the **one deliberate exception**: Terraform can't create the storage that holds its own state — it would need that storage to exist before it could run. So we bootstrap it **once, by hand, with `az`**. This is the standard, accepted pattern. `backend.tf` documents it so no future reader files it as a bug.

### Azure AD auth, not storage keys
A Storage account has two ways in: **shared keys** (a long-lived secret) or **Azure AD identities** (RBAC). We use Azure AD — `use_azuread_auth = true` in `backend.tf`. Terraform authenticates as the `medisync-admin` service principal (the `ARM_*` env vars you already dot-source) and reaches the blob through the **Storage Blob Data Contributor** role. No key is ever fetched, stored, or committed — consistent with `context.md` rule 5.

### Where the account lives
We put the state Storage account in the existing `rg-medisync-prod` resource group — one resource group for the whole project, and the `medisync-admin` SP already has access there. Its name, `medisynctfstate2n3ccl`, reuses the same `2n3ccl` suffix as the Cosmos account purely so the project's globally-unique names look consistent.

---

## Step 1 — Sign into the Azure CLI as yourself

The bootstrap creates a **role assignment**, which needs Owner / User Access Administrator rights. The `medisync-admin` SP only has *Contributor* — it cannot grant roles. So run this as **you** (the subscription owner), not the SP.

```powershell
az login
az account set --subscription 4547eb5a-b286-4639-bcb7-2aa8a1fba2ea
az account show --query user.name -o tsv
```

The last line must print **your** account (`rizam.ibrahim.my@gmail.com`) — not an application/SP id.

> Your `az` CLI login is completely separate from the `ARM_*` env vars Terraform uses. Logging in here as yourself does not change which identity Terraform runs as.

---

## Step 2 — Bootstrap the state Storage account

Run this whole block in PowerShell. It's idempotent — safe to re-run if a line fails midway.

```powershell
$SA  = "medisynctfstate2n3ccl"
$RG  = "rg-medisync-prod"
$LOC = "southeastasia"

# 2a. Make sure the Storage resource provider is registered (usually already is)
az provider register --namespace Microsoft.Storage

# 2b. Create the Storage account — locally-redundant, TLS 1.2 min, no public blobs
az storage account create `
  --name $SA --resource-group $RG --location $LOC `
  --sku Standard_LRS --kind StorageV2 `
  --min-tls-version TLS1_2 `
  --allow-blob-public-access false `
  --https-only true

# 2c. Turn on blob versioning — keeps a history of every state write, so a
#     corrupted or bad state can be rolled back to a previous version.
az storage account blob-service-properties update `
  --account-name $SA --resource-group $RG `
  --enable-versioning true

# 2d. Create the container that holds the state blob
az storage container create --name tfstate --account-name $SA --auth-mode key

# 2e. Grant the medisync-admin SP data-plane access to the state blobs
$SP   = az ad sp list --display-name "medisync-admin" --query "[0].appId" -o tsv
$SAID = az storage account show --name $SA --resource-group $RG --query id -o tsv
az role assignment create `
  --assignee $SP `
  --role "Storage Blob Data Contributor" `
  --scope $SAID
```

> **Wait ~1–2 minutes after Step 2e.** Azure RBAC assignments take a short while to propagate. If you run `terraform init` immediately you may get a `403` — that's the role not being live yet, not a real failure.

If `2b` fails with `StorageAccountAlreadyTaken`, the global name is taken — pick another (e.g. add digits: `medisynctfstate2n3ccl2`), update **both** the `$SA` line above **and** `storage_account_name` in `infra/backend.tf`, and re-run.

---

## Step 3 — Review `infra/backend.tf`

The file was rewritten for you. Open it and confirm it points at the account you just created:

```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-medisync-prod"
    storage_account_name = "medisynctfstate2n3ccl"
    container_name       = "tfstate"
    key                  = "infra.tfstate"
    use_azuread_auth     = true
  }
}
```

`key` is the name of the state *blob* inside the container. `infra/probe/` keeps its own local state — we don't migrate the throwaway probe.

---

## Step 4 — Migrate the state

From the repo root:

```powershell
. .\.temp\envrc.ps1
cd infra
terraform init -migrate-state
```

Terraform detects that the backend changed from `local` to `azurerm` and asks:

```
Do you want to copy existing state to the new backend?
  ...
  Enter a value:
```

Type **`yes`**. Terraform uploads your current 6-resource state to the blob.

Expected tail:

```
Successfully configured the backend "azurerm"! Terraform will automatically
use this backend unless the backend configuration changes.
...
Terraform has been successfully initialized!
```

---

## Step 5 — Verify

```powershell
terraform state list
terraform plan
```

- `terraform state list` should print all **6 resources** (`random_string.suffix`, the Cosmos account, database, and 3 containers) — this list is now coming *from the blob*.
- `terraform plan` should report **`No changes.`** — proof the migrated state still matches reality.

Eyeball it in the Portal too: **Storage accounts → medisynctfstate2n3ccl → Containers → tfstate** — you'll see one blob, `infra.tfstate`.

---

## Step 6 — Remove the stale local state file

The old local files are now superseded and ignored. Delete them to avoid confusion (they're gitignored, so this has no effect on git):

```powershell
Remove-Item terraform.tfstate, terraform.tfstate.backup -ErrorAction SilentlyContinue
```

From here on, state lives only in the blob.

---

## Step 7 — (Optional) Harden: disable shared-key access

Right now the account still accepts its shared keys. Terraform doesn't use them (it's on Azure AD), so you can switch them off entirely for a stronger posture:

```powershell
az storage account update --name $SA --resource-group $RG --allow-shared-key-access false
```

After this, **all** access is Azure AD only. Terraform keeps working (the SP has the data role). The trade-off: any `az storage ...` command you run by hand must use `--auth-mode login`, and your own account would need a blob data role to browse blobs in the Portal. Fine to skip for now and do later.

---

## Step 8 — Commit

From the repo root:

```powershell
cd ..
git status
git add infra/backend.tf docs/runbooks/07-remote-state-backend.md
git commit -m "infra: migrate terraform state to azure blob backend + runbook 07"
git push
```

Only `backend.tf` and the runbook should appear — state files stay gitignored.

---

## Step 9 — Final state checklist

- [ ] Storage account `medisynctfstate2n3ccl` exists in `rg-medisync-prod` with a `tfstate` container.
- [ ] Blob versioning is enabled on the account.
- [ ] `medisync-admin` SP has **Storage Blob Data Contributor** on the account.
- [ ] `terraform init -migrate-state` succeeded; backend is `azurerm`.
- [ ] `terraform state list` shows 6 resources, read from the blob.
- [ ] `terraform plan` reports **No changes**.
- [ ] `infra.tfstate` blob is visible in the Portal.
- [ ] Local `terraform.tfstate` / `.backup` deleted; nothing state-related committed.

---

## What's next

Runbook **`08-terraform-cicd.md`** — the CI/CD pipeline. With state now in a place CI can reach, we'll:
- add federated credentials to `medisync-deploy` for **pull-request** and **environment** OIDC subjects,
- grant `medisync-deploy` the same **Storage Blob Data Contributor** role on this account,
- add a workflow that runs `terraform plan` on every PR touching `infra/**` and posts the result,
- add a workflow that runs a **manually-approved** `terraform apply` on merges to `main`.

---

## Troubleshooting

### `terraform init` fails: `Error: Failed to get existing workspaces` / `403` / `AuthorizationPermissionMismatch`
The `Storage Blob Data Contributor` assignment from Step 2e hasn't propagated yet, or wasn't created. Wait 2 minutes and retry. Confirm it exists:
```powershell
az role assignment list --assignee $SP --scope $SAID -o table
```

### `terraform init` fails: `Backend configuration changed`
Expected the first time — that's why the command is `terraform init -migrate-state`, not plain `init`. If you already ran plain `init` and it errored, just run it again with `-migrate-state`.

### `az storage account create` fails: `StorageAccountAlreadyTaken`
The global name is taken. Pick a new unique name, update `$SA` **and** `storage_account_name` in `backend.tf`, re-run Step 2.

### `az storage container create` fails: `AuthorizationFailure` or asks for a key
Shared-key access may already be disabled, or you're not logged in as an owner. Re-run `az login` as yourself; if you intentionally disabled keys, add `--auth-mode login` (and ensure your account has a blob data role).

### `terraform plan` shows resources to **destroy/recreate** right after migration
The migration didn't actually carry the state over — you may have answered `no` to the copy prompt, or init created fresh empty state. **Do not apply.** Restore: copy `terraform.tfstate.backup` back to `terraform.tfstate`, set the backend back to local, and re-run `terraform init -migrate-state` answering `yes`.

### Lost / corrupted state blob
Blob versioning (Step 2c) has your back: in the Portal, open the `infra.tfstate` blob → **Versions** tab → restore a previous version.

---

## Related runbooks
- [[06-first-resource-cosmos]] — created the resources whose state we just migrated.
- `08-terraform-cicd.md` — the CI pipeline that depends on this remote backend.
