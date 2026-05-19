# Runbook 03 — Azure CLI defaults, Functions Core Tools, Terraform auth

> **Purpose:** Get your local dev environment fully wired to Azure as `medisync-admin`, so the next time you run `terraform plan` or `func start` it Just Works without re-pasting secrets.
>
> By the end you'll have:
> 1. **Azure Functions Core Tools (`func`)** installed for local Function runtime + scaffolding.
> 2. **Azure CLI defaults** set (default subscription, default RG, default region) so you stop repeating `--subscription` and `--resource-group` on every command.
> 3. **A local `.envrc`** with `ARM_*` env vars that lets Terraform authenticate as `medisync-admin` non-interactively.
> 4. **A passing `terraform plan` against a no-op `provider {}` block** proving the auth chain works end-to-end.
>
> **Estimated time:** 25–40 minutes.
> **Prerequisite:** Runbooks 01 + 02 complete.

---

## Concepts (read once)

- **Azure Functions Core Tools (`func`)** = the local runtime that runs Function apps on your laptop (`func start`), plus scaffolding for new functions (`func init`, `func new`). Different from the cloud Functions service; this is just the dev tool.
- **Terraform `azurerm` provider** authenticates via *one of* these methods, in order:
  1. Azure CLI (`az login`) — convenient but uses your interactive identity, not the SP.
  2. **Service principal + client secret via env vars** — what we'll use. Reproducible, scriptable, no MFA prompts.
  3. Managed identity / OIDC / federated tokens — for CI runners (runbook 04 will use this).
- **`ARM_*` env vars** = Terraform's contract for SP auth: `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`. Set these and Terraform skips all other auth methods.
- **`.envrc`** = a per-folder env file. Pattern works two ways:
  - With [direnv](https://direnv.net/) installed: `cd` into the folder and the vars load automatically.
  - Without direnv: `. .\.envrc` (dot-source) in PowerShell to load on demand. We'll use this — no extra tool to install.

---

## Step 1 — Install Azure Functions Core Tools

> **Deferrable.** `func` is only needed when you start writing Function code (a few runbooks away). If install times out or hits network issues, **skip this step**, finish Steps 2–6, and circle back. The probe in Step 5 does *not* require `func`.

The recommended install on Windows is via npm (cross-version, easy to upgrade). You already have Node installed.

In PowerShell:

```powershell
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

Why version `4`: it's the current major version, supports Python 3.12 (our planned runtime) and the v2 programming model for Python.

Verify:

```powershell
func --version
```

Expected: `4.x.xxxx` — anything `4.x` is fine.

```powershell
func templates list --language python
```

Should print a list of trigger templates (HTTP, Timer, Queue, etc.). If this errors, the install didn't fully finish — close PowerShell, reopen, retry.

> **Alternative install:** if npm complains about EACCES or you'd rather not use npm globals, use winget instead:
> `winget install Microsoft.AzureFunctionsCoreTools` — same result, slower to upgrade.

---

## Step 2 — Set Azure CLI defaults

Right now every `az` command needs `--subscription` because the SP login doesn't persist a default. Fix that.

First, log in as `medisync-admin` if you're signed out:

```powershell
az login --service-principal `
  --username d18bde6a-a642-462d-95da-182a8fb5529c `
  --password '<paste-secret-from-azureid.md>' `
  --tenant 382f042a-f53e-4419-aec8-cc4773f2169b
```

Then set the defaults:

```powershell
az account set --subscription 4547eb5a-b286-4639-bcb7-2aa8a1fba2ea
az configure --defaults group=rg-medisync-prod location=southeastasia
```

Verify:

```powershell
az configure --list-defaults
```

Expected output (table form):

```
Name      Source                        Value
--------  ----------------------------  -----------------
group     C:\Users\Admin\.azure\config  rg-medisync-prod
location  C:\Users\Admin\.azure\config  southeastasia
```

Now `az resource list` (no flags) implicitly scopes to the current subscription, and creation commands like `az storage account create --name X` implicitly land in `rg-medisync-prod` in `southeastasia`.

> ℹ️ Defaults live in `C:\Users\Admin\.azure\config` — they survive shell restarts and SP re-logins. They're per-machine, not per-SP.

---

## Step 3 — Create the gitignored `.envrc`

This file holds the SP creds for Terraform. We're putting it in `.temp/` so it's covered by the existing gitignore.

> **Why `.temp/` and not the repo root:** if you do `dot-source .\.envrc` from the wrong directory you might commit it by accident. `.temp/` is the dead-zone.

Create `c:\Users\Admin\Documents\Rizam\Ai Agent Project\AWS_ecommerce\.temp\envrc.ps1`:

```powershell
# MediSync — medisync-admin SP credentials for Terraform azurerm provider.
# Dot-source this file in PowerShell to load:    . .\.temp\envrc.ps1
# DO NOT COMMIT. .temp/ is gitignored.

$env:ARM_CLIENT_ID       = "<medisync-admin-application-client-id>"
$env:ARM_CLIENT_SECRET   = "<medisync-admin-client-secret-value-from-temp-azureid-md>"
$env:ARM_TENANT_ID       = "<your-entra-tenant-id>"
$env:ARM_SUBSCRIPTION_ID = "<your-subscription-id>"

Write-Host "Azure SP env loaded: medisync-admin -> sub 4547eb5a... (rg-medisync-prod, southeastasia)" -ForegroundColor Green
```

Verify the file is gitignored: check `.gitignore` already contains `.temp/` (it should — set up earlier). If not, add it now.

Load it in your current shell:

```powershell
. ".\.temp\envrc.ps1"
```

(Dot-space-quote-path — the leading `.` is PowerShell's dot-source operator, not a relative-path dot.)

Verify the vars are set:

```powershell
$env:ARM_CLIENT_ID
$env:ARM_SUBSCRIPTION_ID
```

Both should echo their GUIDs.

> **Pattern for next time:** every fresh PowerShell window, `cd` into the project folder and run `. .\.temp\envrc.ps1`. Two seconds. Or wrap it into a PowerShell `$PROFILE` function if you do it daily.

---

## Step 4 — Write a probe Terraform config

We're not provisioning anything yet — just proving the provider can authenticate. Create `c:\Users\Admin\Documents\Rizam\Ai Agent Project\AWS_ecommerce\infra\probe\main.tf`:

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}

  # Disable subscription-scoped auto-registration of resource providers.
  # Our SP is Contributor at RG scope only (least privilege), so the default
  # behavior would 403 on every Microsoft.* registration call.
  # We register only the providers we need explicitly, using a higher-privilege
  # identity (portal or `az provider register` as Global Admin) — see Step 5b.
  resource_provider_registrations = "none"
}

# Read-only data source — proves auth + read permission on the RG.
data "azurerm_resource_group" "prod" {
  name = "rg-medisync-prod"
}

output "rg_id" {
  value = data.azurerm_resource_group.prod.id
}

output "rg_location" {
  value = data.azurerm_resource_group.prod.location
}
```

> Why a `data` source and not a `resource`: data sources only *read*. If something is wrong with the SP role assignment, we get a clear "AuthorizationFailed" without creating any cloud objects to clean up.

---

## Step 5 — Run the probe

In the same PowerShell window where `.envrc` is loaded:

```powershell
cd "c:\Users\Admin\Documents\Rizam\Ai Agent Project\AWS_ecommerce\infra\probe"
terraform init
terraform plan
```

**Expected `terraform init` output:** "Terraform has been successfully initialized!" — downloads the azurerm provider plugin (~50 MB) into `.terraform/`.

**Expected `terraform plan` output:**
```
data.azurerm_resource_group.prod: Reading...
data.azurerm_resource_group.prod: Read complete after 1s [id=/subscriptions/4547eb5a.../resourceGroups/rg-medisync-prod]

Changes to Outputs:
  + rg_id       = "/subscriptions/4547eb5a-b286-4639-bcb7-2aa8a1fba2ea/resourceGroups/rg-medisync-prod"
  + rg_location = "southeastasia"

No changes. Your infrastructure matches the configuration.
```

If that's what you see → SP auth, RBAC, region, env vars all work end-to-end. ✅

Apply isn't strictly necessary — `plan` already exercised authentication. But for completeness:

```powershell
terraform apply -auto-approve
```

It creates *no resources* (the config has none) but writes the outputs to state. Safe.

---

## Step 6 — Add infra/probe paths to `.gitignore` carefully

The `.terraform/` plugin cache and the `terraform.tfstate` file should be gitignored — the cache is platform-specific, and **`terraform.tfstate` will eventually contain secrets**. Even an empty state file from this probe sets the right precedent.

Open `.gitignore` and confirm (or add) these lines:

```gitignore
# Terraform
**/.terraform/
**/.terraform.lock.hcl
*.tfstate
*.tfstate.*
*.tfplan
```

> **Why `.terraform.lock.hcl` is debated:** Terraform docs say *commit it* so collaborators pin to identical provider versions. Solo-dev tradeoff: ignore it for now to keep churn low; flip to committed when you start working with someone else.

---

## Step 7 — Final state checklist

- [ ] `func --version` prints `4.x`.
- [ ] `az configure --list-defaults` shows `group=rg-medisync-prod`, `location=southeastasia`.
- [ ] `.temp\envrc.ps1` exists, sets four `ARM_*` env vars, and is gitignored (covered by `.temp/`).
- [ ] `infra\probe\main.tf` exists.
- [ ] `terraform plan` returns "No changes" with `rg_id` and `rg_location` in the proposed outputs.

---

## What's next

Runbook **`04-cicd-github-actions.md`** — wire `medisync-deploy` and the federated credential into a real GitHub Actions workflow. Includes:
- Repo secrets (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` — IDs, no secret values)
- `permissions: id-token: write` block
- `azure/login@v2` usage
- A "hello world" job that runs `az group show --name rg-medisync-prod` from CI to prove federated auth works

(Blocked on: pushing the repo to GitHub. That'll happen after the folder rename + git init pass.)

---

## Troubleshooting

### `func` install fails with EACCES or permission errors
You're likely running PowerShell without admin privileges and npm's global prefix is in a protected dir. Either run PowerShell as Administrator and retry, or set npm's prefix to a user-writable dir:
```powershell
npm config set prefix "$env:USERPROFILE\.npm-global"
# Then add %USERPROFILE%\.npm-global to PATH (System Properties → Environment Variables)
```

### `terraform init` fails with "Failed to query available provider packages"
Network / firewall blocking `registry.terraform.io`. Test with `curl https://registry.terraform.io`. If corporate proxy, set `HTTP_PROXY` / `HTTPS_PROXY`.

### `terraform plan` returns "Error: building AzureRM Client: please ensure you have either: a Service Principal..."
ARM_* env vars aren't loaded in this shell. Re-run `. .\.temp\envrc.ps1` and confirm `$env:ARM_CLIENT_ID` echoes a GUID.

### `terraform plan` returns dozens of "AuthorizationFailed ... /register/action" errors
This is the expected first-run failure with a least-privilege SP. The v4 azurerm provider tries to auto-register every resource provider at the subscription scope. Fix: add `resource_provider_registrations = "none"` to the `provider "azurerm"` block (see Step 4 config). Then later, when you actually need a service (e.g. Microsoft.Web for Functions), register it once as a higher-privilege identity:
```powershell
# Sign back in interactively as Global Admin, then:
az provider register --namespace Microsoft.Web
az provider show --namespace Microsoft.Web --query registrationState
```

### `terraform plan` returns "AuthorizationFailed: does not have authorization to perform action Microsoft.Resources/subscriptions/resourceGroups/read"
The `medisync-admin` Contributor role assignment didn't stick or is on the wrong scope. Re-verify in Portal: `rg-medisync-prod` → IAM → Role assignments → look for `medisync-admin` row with Role = Contributor, Scope = This resource.

### `terraform plan` returns "Error: client secret used by client_id ... is invalid"
The secret in `.envrc` doesn't match what's in Entra. Either it was retyped wrong or it expired. Re-check `.temp\azureid.md`, and if needed create a fresh secret per runbook 02 Step 3.

### Multiple subscriptions show up in `az login` output
Not applicable now (you only have one), but future-proof: always use `az account set --subscription <ID>` to pin and `az account show` to confirm the active one before running commands.
