# Runbook 09 — Function Apps, Event Grid & First Deploy

**Goal:** provision the three Azure Function Apps, their shared platform
(storage, consumption plan, Application Insights), the Event Grid topic, and
the reconciled Cosmos containers — then deploy the scaffolded service code and
wire the match Saga end to end.

**Prerequisites:** runbooks 01–08 complete. The Terraform for this runbook
already exists in `infra/` (`functions.tf`, `identity.tf`, `eventgrid.tf`,
updated `cosmos.tf`). The three services are scaffolded under `services/`.

**What gets created**

| Resource | Notes |
|---|---|
| `azurerm_log_analytics_workspace.main` | `medisync-prod-logs`, 30-day retention |
| `azurerm_application_insights.main` | `medisync-prod-appi`, shared by all 3 apps |
| `azurerm_storage_account.functions` | `medisyncfunc2n3ccl`, shared runtime storage |
| `azurerm_service_plan.functions` | `medisync-prod-func-plan`, Linux **Y1 consumption** |
| `azurerm_linux_function_app.{user,inventory,match}` | Python 3.12, system-assigned MI |
| `azurerm_eventgrid_topic.main` | `medisync-prod-events` |
| `azurerm_cosmosdb_sql_container.{profiles,inventory,requests}` | **replaces** the runbook-06 placeholders |
| Cosmos data-plane + Event Grid role assignments | least-privilege, per service |

**Cost:** ~$0/month. Functions consumption (1M free executions), Event Grid
(100k free operations), serverless Cosmos and Log Analytics (5 GB free) all
sit inside permanent free grants at portfolio traffic.

> ⚠️ **This apply is mildly destructive.** The clean-slate Cosmos decision
> means Terraform **destroys** the empty `donors` and `matches` containers and
> **recreates** `requests` with partition key `/id`. No data is lost (the
> placeholders were never populated), but the plan will show deletions —
> expected.

---

## Step 1 — Register resource providers (Global Admin)

The `medisync-deploy` SP only has Contributor on the resource group and
**cannot self-register** providers (the lesson from runbook 06). Register them
once with your own Global Admin account.

1. Sign in and select the subscription:
   ```
   az login
   ```
   ```
   az account set --subscription 4547eb5a-b286-4639-bcb7-2aa8a1fba2ea
   ```
2. Register the four new providers (each is a single-line command):
   ```
   az provider register --namespace Microsoft.Web
   ```
   ```
   az provider register --namespace Microsoft.EventGrid
   ```
   ```
   az provider register --namespace Microsoft.Insights
   ```
   ```
   az provider register --namespace Microsoft.OperationalInsights
   ```
   (`Microsoft.Storage` and `Microsoft.DocumentDB` were registered in
   runbooks 07 and 06.)
3. Registration takes a minute or two. Confirm each reads `Registered`:
   ```
   az provider show --namespace Microsoft.Web --query registrationState -o tsv
   ```
   Repeat for `Microsoft.EventGrid`, `Microsoft.Insights`,
   `Microsoft.OperationalInsights`. Do not continue until all four say
   `Registered`.

---

## Step 2 — Grant the deploy SP permission to assign roles

`identity.tf` creates an **EventGrid Data Sender** role assignment. Creating
any role assignment needs `Microsoft.Authorization/roleAssignments/write`,
which **Contributor does not have**. Grant the `medisync-deploy` SP the
**Role Based Access Control Administrator** role, scoped to the resource group.

1. Find the `medisync-deploy` app (client) id — it is recorded in
   `.temp/azureid.md` (runbook 02). Or look it up:
   ```
   az ad sp list --display-name medisync-deploy --query "[0].appId" -o tsv
   ```
2. Assign the role at resource-group scope (single line — substitute the id):
   ```
   az role assignment create --assignee <medisync-deploy-appId> --role "Role Based Access Control Administrator" --scope /subscriptions/4547eb5a-b286-4639-bcb7-2aa8a1fba2ea/resourceGroups/rg-medisync-prod
   ```
3. Confirm it landed:
   ```
   az role assignment list --assignee <medisync-deploy-appId> --resource-group rg-medisync-prod -o table
   ```
   You should see both `Contributor` and `Role Based Access Control Administrator`.

> Hardening note: RBAC Admin can be granted with a *condition* that limits
> which roles it may assign. Skipped here for simplicity at portfolio scale —
> the scope is one resource group, not the subscription.

---

## Step 3 — Apply the infrastructure (via the CI pipeline)

The Terraform lives under `infra/**`, so the runbook-08 pipeline handles it —
no local apply needed.

1. Branch, commit the `infra/` changes, and open a PR:
   ```
   git checkout -b feat/functions-eventgrid-infra
   ```
   ```
   git add infra/ docs/runbooks/09-functions-eventgrid-deploy.md
   ```
   ```
   git commit -m "infra: provision function apps, event grid + runbook 09"
   ```
   ```
   git push -u origin feat/functions-eventgrid-infra
   ```
   Then open the PR on GitHub.
2. `terraform-plan.yml` posts the plan as a PR comment. **Review it.** Expect:
   `donors` and `matches` **destroyed**, `requests` **replaced**, and ~13
   resources **added**. `enable_match_event_subscription` is `false`, so the
   Event Grid *subscription* is **not** in this plan — correct (see Step 5).
3. Merge the PR. `terraform-apply.yml` runs under the `production`
   environment and pauses for approval. Approve it. The apply takes 3–5
   minutes (Function Apps are the slow part).
4. Read the new outputs from the apply log, or locally:
   ```
   . .\.temp\envrc.ps1
   ```
   ```
   terraform -chdir=infra output function_app_names
   ```
   The names follow `medisync-prod-<service>-func-2n3ccl`.

---

## Step 4 — Deploy the service code

Each Function App now exists but is **empty**. Publish the scaffolded code with
the Core Tools (remote build installs `requirements.txt` via Oryx).

Make sure you are signed in (`az login`), then from the repo root:

```
func azure functionapp publish medisync-prod-user-func-2n3ccl
```
```
func azure functionapp publish medisync-prod-inventory-func-2n3ccl
```
```
func azure functionapp publish medisync-prod-match-func-2n3ccl
```

Run each from inside the matching service folder (`services/user`,
`services/inventory`, `services/match`) — `func` publishes the current
directory. Each publish prints the deployed functions; confirm the counts:
user **4**, inventory **4**, match **10**.

Smoke-test the HTTP health probes (no auth — the apps are `ANONYMOUS`):

```
curl https://medisync-prod-user-func-2n3ccl.azurewebsites.net/api/health
```

Expect `{"status": "ok", "service": "user"}`. Repeat for inventory and match.

---

## Step 5 — Wire the Event Grid subscription

Now that `on_emergency_request` exists in the deployed match app, Event Grid
can validate it. Flip the toggle and apply again.

1. In `infra/variables.tf`, change the `enable_match_event_subscription`
   default from `false` to `true`.
2. PR it the same way as Step 3:
   ```
   git checkout -b feat/enable-match-subscription
   ```
   ```
   git commit -am "infra: enable EmergencyRequestCreated -> match subscription"
   ```
   Open the PR, review the plan (one resource added —
   `azurerm_eventgrid_event_subscription.emergency_request_to_match[0]`),
   merge, approve the apply.

---

## Step 6 — Smoke-test the Saga end to end

1. Seed a compatible inventory unit (note the `id` and `geohash_prefix` in the
   response):
   ```
   curl -X POST https://medisync-prod-inventory-func-2n3ccl.azurewebsites.net/api/inventory -H "Content-Type: application/json" -d "{\"hospital_id\":\"HOSP-01\",\"item_type\":\"Blood\",\"sub_type\":\"O-\",\"expiry_date\":\"2026-12-01\",\"location\":{\"lat\":3.04,\"lng\":101.45}}"
   ```
2. Submit an emergency request:
   ```
   curl -X POST https://medisync-prod-match-func-2n3ccl.azurewebsites.net/api/request/emergency -H "Content-Type: application/json" -d "{\"hospital_id\":\"HOSP-01\",\"blood_type\":\"O+\",\"units\":1,\"urgency\":\"Critical\",\"location\":{\"lat\":3.04,\"lng\":101.45}}"
   ```
   The response is `202` with a `request_id`.
3. Poll the request — within a few seconds the Saga should drive it to
   `Matched`:
   ```
   curl https://medisync-prod-match-func-2n3ccl.azurewebsites.net/api/request/<request_id>
   ```
4. Open **Application Insights → `medisync-prod-appi` → Application Map**. You
   should see the match app calling the inventory app — the cross-service
   trace (context.md §8). Screenshot it for the README.

---

## Troubleshooting

### `terraform apply` fails with `403` / `AuthorizationFailed` on a provider
A resource provider from Step 1 is not registered yet. Re-check all four read
`Registered` and re-run the workflow.

### `terraform apply` fails creating the EventGrid role assignment
The `Role Based Access Control Administrator` grant from Step 2 is missing or
has not propagated (can take a few minutes). Confirm with the
`az role assignment list` command in Step 2, then re-run the workflow.

### `func publish` fails the remote build
Confirm the service folder has `requirements.txt` and `host.json`, and that
the app's runtime is Python 3.12 (`az functionapp config show --name <app>
--resource-group rg-medisync-prod --query linuxFxVersion`).

### Event Grid subscription creation fails endpoint validation
The match service code is not deployed, or `on_emergency_request` was renamed.
Step 4 **must** come before Step 5. Re-publish the match app and re-apply.

### Saga request stays `Pending`
The Event Grid subscription is not delivering. Check Step 5 applied, and look
at the match app's logs in Application Insights for `on_emergency_request`
invocations. A `Cosmos 403` in the logs means the data-plane role assignment
is still propagating — wait a few minutes and retry.

### Next plan wants to remove `WEBSITE_RUN_FROM_PACKAGE`
It should not — `functions.tf` has `ignore_changes` for that key. If you see
other `func`-added settings drift, add them to the same `lifecycle` block.

---

## Result

- Three Function Apps live, code deployed, health probes green.
- Event Grid routes `EmergencyRequestCreated` into the match Saga.
- Cosmos containers match the application code (`profiles`, `inventory`,
  `requests`).
- One end-to-end trace visible in Application Insights.

This completes the **infrastructure + first deploy**. Remaining work: real
Entra External ID authentication, ACS Email, and the Next.js frontend.
