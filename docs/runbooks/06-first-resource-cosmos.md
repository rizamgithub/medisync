# Runbook 06 — First real resource: Cosmos DB (serverless)

> **Purpose:** Provision MediSync's first piece of real infrastructure — a serverless Cosmos DB for NoSQL account with one database and three containers — and run `terraform apply` for the first time.
>
> By the end you'll have:
> 1. The `Microsoft.DocumentDB` resource provider registered on the subscription.
> 2. A serverless Cosmos DB account, a `medisync` database, and `donors` / `requests` / `matches` containers — all managed by Terraform.
> 3. Three new `terraform output` values (account name, endpoint, database name).
> 4. Your first non-empty `terraform.tfstate`.
>
> **Estimated time:** 20–35 minutes (most of it waiting on Azure to build the Cosmos account).
> **Prerequisite:** Runbook 05 complete. `medisync-admin` SP secret loaded via `. .\.temp\envrc.ps1`.
> **Cost:** ~**$0.00/month idle**. Serverless Cosmos bills per request (~$0.25 per million RU) plus storage (~$0.25/GB/month). At portfolio scale this is single-digit cents. Nothing here touches the $5 budget cap meaningfully.

---

## Concepts (read once)

### Why serverless, not free tier
Cosmos has two billing modes that can be $0-ish:
- **Free tier** — 1000 RU/s + 25 GB free, but it is *provisioned-throughput* mode. One free-tier account per subscription.
- **Serverless** — no provisioned throughput at all; you pay only for requests actually consumed. Idle cost is genuinely $0.

We pick **serverless**. It's truly $0 when nothing is calling it (the realistic state of a portfolio project most of the time), and serverless is mutually exclusive with free tier anyway. The trade-off: serverless caps at lower throughput and 1 TB/container — irrelevant at our scale.

### Resource providers must be registered first
Every Azure service is fronted by a *resource provider* — Cosmos is `Microsoft.DocumentDB`. A provider must be registered on the **subscription** before Terraform can create resources of that type. Our `medisync-admin` SP is only **Contributor on the resource group**, which is not enough to register a provider (that's a subscription-scope action). So **you** register it once, as the subscription owner (your Microsoft account). This is Step 1, and it's a one-time action per provider.

### Partition keys are a permanent decision
A Cosmos container stores documents across physical partitions, and the **partition key** decides which partition each document lands in. Good partition keys are:
- **high cardinality** (many distinct values → even spread), and
- **present in your most frequent queries' filter** (so those queries stay on one partition instead of fanning out — fan-out costs more RU).

A partition key **cannot be changed after the container is created.** Changing `partition_key_paths` in Terraform = destroy + recreate the container = data loss. So this runbook commits to choices now:

| Container  | Partition key   | Why                                                                                     |
|------------|-----------------|-----------------------------------------------------------------------------------------|
| `donors`   | `/bloodType`    | The dominant match query is "find donors of blood type X".                              |
| `requests` | `/bloodType`    | Same query path — requests are filtered by the blood type they need.                    |
| `matches`  | `/requestId`    | Matches are almost always read as "all matches for request X" → stays single-partition. |

**Known trade-off on `/bloodType`:** ABO/Rh has only ~8 distinct values, so it's *low cardinality* and could create hot partitions at very large scale. For Phase 1 / portfolio scale this is fine and is a perfectly defensible answer in an interview — *as long as you can name the trade-off*. If MediSync ever needed real scale, the fix would be a synthetic composite key (e.g. `bloodType-region`).

---

## Step 1 — Register the `Microsoft.DocumentDB` provider (as subscription owner)

Do this as **yourself** (the Microsoft account `rizam.ibrahim.my@gmail.com` that owns the subscription) — *not* the service principal.

### Option A — Azure Portal (recommended, visual)

1. Go to <https://portal.azure.com> → search **Subscriptions** → click **Azure subscription 1**.
2. In the left menu, under **Settings**, click **Resource providers**.
3. In the filter box type `DocumentDB`.
4. Select the **Microsoft.DocumentDB** row → click **Register** at the top.
5. The state goes `Registering` → `Registered`. Refresh after ~1–3 minutes to confirm **Registered**.

### Option B — Azure CLI

`az` uses its *own* login, separate from the `ARM_*` env vars Terraform uses. Make sure you're logged in as yourself:

```powershell
az login                     # opens browser — sign in as rizam.ibrahim.my@gmail.com
az account show --query user.name -o tsv     # must show YOUR account, not an app id
az provider register --namespace Microsoft.DocumentDB
```

Poll until it reports `Registered`:

```powershell
az provider show --namespace Microsoft.DocumentDB --query registrationState -o tsv
```

> Registration is idempotent — running it again when already registered is harmless.

---

## Step 2 — Review `infra/cosmos.tf`

The file was written for you. Open `infra/cosmos.tf` and skim it so you understand what `apply` will create:

- `random_string.suffix` — a 6-char suffix making the globally-unique account name unique.
- `azurerm_cosmosdb_account.main` — serverless, Session consistency, single region.
- `azurerm_cosmosdb_sql_database.main` — the `medisync` database.
- `azurerm_cosmosdb_sql_container.{donors,requests,matches}` — the three containers with the partition keys from the table above.

`infra/outputs.tf` also gained three Cosmos outputs. Account **keys are intentionally not output** — Functions will use managed identity later.

---

## Step 3 — Load credentials and plan

From the repo root:

```powershell
. .\.temp\envrc.ps1
cd infra
terraform plan
```

Expected: **6 resources to add, 0 to change, 0 to destroy**, plus 3 new outputs:

```
Plan: 6 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + cosmosdb_account_name  = (known after apply)
  + cosmosdb_database_name = "medisync"
  + cosmosdb_endpoint      = (known after apply)
```

The 6 resources: 1 `random_string` + 1 account + 1 database + 3 containers.

---

## Step 4 — Apply (first real `terraform apply`)

```powershell
terraform apply
```

Review the plan, then type **`yes`** when prompted.

> **Be patient.** Creating a Cosmos account takes **5–10 minutes** — this is normal Azure provisioning time, not a hang. The containers finish quickly once the account exists. Don't Ctrl-C; if interrupted, just re-run `terraform apply` (it's idempotent and resumes).

When it finishes:

```
Apply complete! Resources: 6 added, 0 changed, 0 destroyed.

Outputs:
cosmosdb_account_name  = "cosmos-medisync-prod-xxxxxx"
cosmosdb_database_name = "medisync"
cosmosdb_endpoint      = "https://cosmos-medisync-prod-xxxxxx.documents.azure.com:443/"
```

---

## Step 5 — Verify

```powershell
terraform output
```

Cross-check in Azure:

```powershell
az cosmosdb show --name (terraform output -raw cosmosdb_account_name) `
  --resource-group rg-medisync-prod `
  --query "{name:name, state:provisioningState, capabilities:capabilities}" -o jsonc
```

`provisioningState` should be `Succeeded` and `capabilities` should list `EnableServerless`.

Or in the portal: **Resource groups → rg-medisync-prod → cosmos-medisync-prod-xxxxxx → Data Explorer** — you should see the `medisync` database with `donors`, `requests`, and `matches` under it.

---

## Step 6 — Commit

From the repo root:

```powershell
cd ..
git status
git add infra/cosmos.tf infra/outputs.tf docs/runbooks/06-first-resource-cosmos.md
git commit -m "infra: provision serverless Cosmos DB + runbook 06"
git push
```

`*.tfstate*` is gitignored — your now-populated state file stays local. (Moving state to an Azure Blob backend is runbook 07's job, before CI can apply.)

---

## Step 7 — Final state checklist

- [ ] `Microsoft.DocumentDB` shows **Registered** on the subscription.
- [ ] `terraform apply` completed: `6 added, 0 changed, 0 destroyed`.
- [ ] `terraform output` shows account name, endpoint, and `medisync` database name.
- [ ] Portal Data Explorer shows the `medisync` database with 3 containers.
- [ ] `infra/terraform.tfstate` is now non-empty and **not** committed to git.
- [ ] `git push` succeeded with only the 3 `.tf` / `.md` files changed.

---

## What's next

Runbook **`07-terraform-cicd.md`** — move Terraform state from your laptop to an **Azure Blob backend**, then wire the GitHub Actions OIDC workflow to run `terraform plan` on every PR and a gated `terraform apply` on merges to `main`. Remote state is the prerequisite: CI can't apply against a state file that only exists on your machine.

---

## Troubleshooting

### `apply` fails: `MissingSubscriptionRegistration` / `The subscription is not registered to use namespace 'Microsoft.DocumentDB'`
Step 1 wasn't done, or registration hadn't finished. Re-check `az provider show --namespace Microsoft.DocumentDB --query registrationState` returns `Registered`, then re-run `terraform apply`.

### `plan`/`apply` fails: `The provided credentials are not authorized...`
You forgot to dot-source the SP env file in this shell. Run `. .\.temp\envrc.ps1` from the repo root and retry.

### `apply` fails: Cosmos account name already taken / `NameAlreadyExists`
Extremely unlikely with the random suffix, but if it happens, force a new suffix:
```powershell
terraform apply -replace="random_string.suffix"
```

### `apply` fails mentioning `throughput` on a serverless account
Serverless accounts reject provisioned throughput. Don't add `throughput` or `autoscale_settings` to the database or container blocks — `cosmos.tf` correctly omits them.

### `apply` seems stuck for 8+ minutes on the Cosmos account
Normal. Account creation legitimately takes 5–10 minutes. Wait it out. Terraform's own timeout is 180 minutes, so it won't give up prematurely.

### Need to start over completely
`terraform destroy` removes everything in `cosmos.tf`. The `Microsoft.DocumentDB` registration is *not* a Terraform resource and stays registered — that's fine and free.

---

## Related runbooks
- [[05-terraform-scaffold]] — the `infra/` layout this builds on.
- `07-terraform-cicd.md` — remote state + CI, next.
