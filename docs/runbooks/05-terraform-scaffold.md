# Runbook 05 — Terraform `infra/` scaffold

> **Purpose:** Lay out the root Terraform module that every future MediSync resource lives in, without provisioning anything. Validate the layout with `terraform init` + `terraform plan` returning **"No changes."**.
>
> By the end you'll have:
> 1. A flat `infra/` root module with one `*.tf` file per bounded concern (identity, cosmos, functions, monitoring, eventgrid, email).
> 2. Shared `providers.tf` / `variables.tf` / `locals.tf` / `outputs.tf` / `backend.tf`.
> 3. A green `terraform plan` against `infra/` that reads the existing `rg-medisync-prod` and proposes zero resource changes.
> 4. The legacy `infra/probe/` left in place as a known-good smoke test.
>
> **Estimated time:** 15–25 minutes.
> **Prerequisite:** Runbooks 01–04 complete. `medisync-admin` SP secret loaded via `. .\.temp\envrc.ps1`.

---

## Concepts (read once)

- **Flat single-stack** layout: one root module under `infra/`, one state file, one `terraform apply`. Chosen over multi-module / multi-stack because the entire project lives in one resource group and one region — module boundaries would be costume jewellery, not load-bearing.
- **One file per concern, not per resource.** `cosmos.tf` will hold the Cosmos account *and* its databases and containers. Keeps related blocks together for readability.
- **Local state, for now.** State lives at `infra/terraform.tfstate` on your laptop (gitignored). Upgrade to Azure Blob backend later — recipe is committed in `backend.tf` as comments. The trigger to upgrade is **whichever of these happens first**: (a) CI runs `terraform apply`, (b) you start working from a second machine, (c) you provision anything genuinely expensive to recreate.
- **Resource-provider registration:** every Azure service has a "resource provider" (`Microsoft.DocumentDB`, `Microsoft.Web`, etc.) that must be registered on the subscription before Terraform can create that resource type. Our SP can't self-register (it's only Contributor on the RG). So `providers.tf` sets `resource_provider_registrations = "none"` and we register each RP **manually as Global Admin** before adding resources of that type. Each `*.tf` skeleton file lists the RP it needs at the bottom as a reminder.

---

## Step 1 — Inspect what was scaffolded

The files were created for you. Skim them so you know what's where.

```
infra/
  providers.tf            # azurerm + azuread + random; resource_provider_registrations = "none"
  backend.tf              # local backend; commented azurerm backend recipe for later
  variables.tf            # project_name, environment, location, resource_group_name, owner_email
  locals.tf               # name_prefix, common_tags map; data block for the existing RG
  outputs.tf              # rg id + location (real resources outputs appended later)
  identity.tf             # placeholder — Key Vault, managed identities
  cosmos.tf               # placeholder — Cosmos account + containers
  functions.tf            # placeholder — storage, plan, function apps
  monitoring.tf           # placeholder — Log Analytics + App Insights
  eventgrid.tf            # placeholder — topics + subscriptions
  email.tf                # placeholder — Communication Services Email
  terraform.tfvars.example
  probe/                  # untouched legacy probe; keep as smoke test
    main.tf
```

The placeholder files are comments only — no resources yet. They exist so the file tree matches future runbooks without you having to `touch` files later.

---

## Step 2 — Load credentials

In PowerShell, from the repo root:

```powershell
. .\.temp\envrc.ps1
```

You should see the green `Azure SP env loaded:` message. Without this, `terraform init` will try interactive `az login` and (depending on cache state) may pick the wrong identity.

---

## Step 3 — Init + plan

```powershell
cd infra
terraform init
terraform plan
```

`terraform init` downloads the `azurerm`, `azuread`, and `random` providers into `infra\.terraform\` (gitignored). First run takes ~30s.

Expected `terraform plan` output:

```
data.azurerm_resource_group.main: Reading...
data.azurerm_resource_group.main: Read complete after 0s [id=/subscriptions/.../resourceGroups/rg-medisync-prod]

Changes to Outputs:
  + resource_group_id       = "/subscriptions/.../resourceGroups/rg-medisync-prod"
  + resource_group_location = "southeastasia"

You can apply this plan to save these new output values to the Terraform state, without changing any real infrastructure.
```

Zero resources to add/change/destroy. Just two new outputs (because state is empty so far).

> **Do NOT run `terraform apply` yet.** There's nothing to apply — applying now would only create state. We'll apply for the first time once a real resource is added (runbook 06).

---

## Step 4 — Sanity check the probe still works

The legacy probe is independent (own state, own `.terraform/`). Confirm we didn't break it:

```powershell
cd ..\probe
terraform plan
```

Should still report the same RG outputs and no changes. The probe stays as a minimal known-good fallback — handy when troubleshooting future provider/auth weirdness.

---

## Step 5 — Commit

From repo root:

```powershell
cd ..\..
git status
git add infra/ docs/runbooks/05-terraform-scaffold.md
git commit -m "infra: scaffold flat single-stack terraform layout + runbook 05"
git push
```

`.terraform/`, `*.tfstate*`, `*.tfvars`, and `.terraform.lock.hcl` are gitignored, so only the `.tf` files + `terraform.tfvars.example` should appear in `git status`.

> **Lock file note:** standard Terraform practice is to commit `.terraform.lock.hcl` for reproducible provider versions. The current `.gitignore` excludes it. **Defer that decision** — once CI runs Terraform (runbook 06) we'll revisit and likely un-ignore the lock files for `infra/` and `infra/probe/`. Until then it's just provider-pinning noise.

---

## Step 6 — Final state checklist

- [ ] `infra/` contains 12 files (6 placeholder concern files + providers/backend/variables/locals/outputs + tfvars.example).
- [ ] `terraform init` in `infra/` succeeds; `.terraform/` directory created.
- [ ] `terraform plan` in `infra/` reports zero resource changes, only the two output additions.
- [ ] `terraform plan` in `infra/probe/` still works (regression check).
- [ ] Nothing in `.temp/` or `infra/.terraform/` or `*.tfstate*` was committed.

---

## What's next

Runbook **`06-first-resource-cosmos.md`** — add the first real resource. We'll register `Microsoft.DocumentDB` as Global Admin, then implement `cosmos.tf` properly: a serverless Cosmos for NoSQL account, one database, and the first container. `terraform apply` runs for real for the first time. Expected cost: ~$0.00 idle, pay-per-request thereafter.

After that, runbook 07 wires the OIDC workflow to run `terraform plan` on every PR and `terraform apply` on merges to `main`.

---

## Troubleshooting

### `terraform init` errors: `Failed to query available provider packages`
Network issue or proxy blocking `registry.terraform.io`. Retry. If persistent, set `TF_REGISTRY_DISCOVERY_RETRY=5` env var and retry.

### `terraform plan` errors: `The provided credentials are not authorized to perform action 'Microsoft.Resources/...' over scope '/subscriptions/...'`
SP secret rotated and `.temp/envrc.ps1` not re-loaded, OR you forgot to dot-source `envrc.ps1` in this shell. Run `. .\.temp\envrc.ps1` from the repo root and retry.

### `terraform plan` errors mentioning `RegistrationRequired` on `Microsoft.Resources`
You removed or forgot the `resource_provider_registrations = "none"` line in `providers.tf`. Restore it — our SP isn't allowed to register RPs at subscription scope.

### Provider downloads hang on Windows / corporate network
Pre-download manually: `terraform providers mirror C:\terraform-providers` from a network where it works, then set `TF_CLI_CONFIG_FILE` to point at a `.terraformrc` with `filesystem_mirror` configured. Overkill unless the registry is unreachable.

### `Error: Backend configuration changed` after un-commenting the azurerm backend later
Run `terraform init -migrate-state` (not just `init`). Terraform refuses to silently move state between backends.
