# Runbook 08 — CI/CD Terraform pipeline

> **Purpose:** Make GitHub Actions run Terraform for you — `terraform plan` automatically on every pull request, and a **manually-approved** `terraform apply` when changes land on `main`. No secrets stored anywhere; authentication is OIDC.
>
> By the end you'll have:
> 1. Two new federated credentials on the `medisync-deploy` app (for pull-request and environment OIDC subjects).
> 2. A GitHub `production` environment that pauses every apply until you approve it.
> 3. `terraform-plan.yml` — plans every infra PR and posts the result as a comment.
> 4. `terraform-apply.yml` — applies on merge to `main`, behind the approval gate.
> 5. The provider lock file committed, so CI and your laptop use identical providers.
>
> **Estimated time:** 30–45 minutes.
> **Prerequisite:** Runbook 07 complete. Remote state in Azure Blob, `medisync-deploy` SP exists with the `main`-branch federated credential from runbook 04.
> **Cost:** **$0.** GitHub Actions is free for public repos; the pipeline provisions nothing by itself.

---

## Concepts (read once)

### OIDC, and why we need *more* federated credentials
GitHub Actions authenticates to Azure with no stored secret: a workflow asks GitHub for a short-lived **OIDC token**, and Azure trusts it *if* a **federated credential** on the app matches the token's `subject` claim.

The catch — the subject changes depending on *how* the workflow runs:

| Workflow runs as… | OIDC token subject | Credential needed |
|---|---|---|
| push to `main` (no environment) | `repo:rizamgithub/medisync:ref:refs/heads/main` | exists — runbook 04 |
| a **pull request** | `repo:rizamgithub/medisync:pull_request` | **new** — this runbook |
| a job with `environment: production` | `repo:rizamgithub/medisync:environment:production` | **new** — this runbook |

So the plan workflow (runs on PRs) and the apply workflow (uses an environment) each need a credential the project doesn't have yet. Step 1 adds both.

### The manual-approval gate
`terraform-apply.yml` declares `environment: production`. A **GitHub Environment** can carry *protection rules* — we add **Required reviewers**. The result: when an apply is triggered, the job **pauses** and emails you; it runs only after you click **Approve**. Nothing reaches Azure without a human in the loop — important on a cost-sensitive project.

> Environment protection rules are **free on public repositories** (yours is public). On a private repo they'd need a paid GitHub plan.

### No `azure/login`, no secrets
These workflows don't use the `azure/login` action. Terraform's `azurerm` provider speaks OIDC natively: set `ARM_CLIENT_ID` / `ARM_TENANT_ID` / `ARM_SUBSCRIPTION_ID` / `ARM_USE_OIDC=true` and it mints and exchanges the token itself. Those three IDs are **not secrets** — they're identifiers — but they're already stored as GitHub Actions secrets from runbook 04, so we reference them from there.

### Why the lock file is now committed
`.terraform.lock.hcl` pins exact provider versions *and* their checksums. Committing it means CI resolves the **same** `azurerm 4.73.0` your laptop uses — no surprise upgrades. It was un-ignored in `.gitignore`, and `terraform providers lock` was run for both `windows_amd64` and `linux_amd64` so the Linux CI runner can verify the providers it downloads.

---

## Step 1 — Azure side: federated credentials + state access

Log into the Azure CLI as the subscription owner (the role assignment needs Owner rights):

```powershell
az login
```

Then run the setup script from the repo root:

```powershell
.\.temp\setup-cicd-azure.ps1
```

It adds the two federated credentials (`github-pull-request`, `github-env-production`) to `medisync-deploy`, and grants that app **Storage Blob Data Contributor** on the state storage account so CI can read/write state. Finishes with a green summary.

> If you'd rather see it visually: **Entra ID → App registrations → medisync-deploy → Certificates & secrets → Federated credentials**. The two new entries should be listed there alongside the runbook-04 `main`-branch one.

---

## Step 2 — GitHub side: create the `production` environment

1. Go to your repo on GitHub → **Settings** → **Environments** (left sidebar) → **New environment**.
2. Name it exactly **`production`** → **Configure environment**.
3. Under **Deployment protection rules**, tick **Required reviewers**. In the box that appears, add **yourself** (`rizamgithub`). You can add up to 6; one is enough.
4. *(Optional, recommended)* Under **Deployment branches and tags**, choose **Selected branches and tags** and add a rule for `main`. This stops anything but `main` from deploying to `production`.
5. Click **Save protection rules**.

The environment name must be **exactly `production`** — it has to match both `terraform-apply.yml` and the `github-env-production` federated credential's subject.

---

## Step 3 — Confirm the repo secrets exist

Repo → **Settings** → **Secrets and variables** → **Actions**. You should already see these three (created in runbook 04):

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

If any are missing, re-add them — values are in `.temp/azureid.md` (these are identifiers, not secrets, but keep them as Actions secrets for tidiness).

---

## Step 4 — Review the workflow files

Two files were written for you — skim them:

- **`.github/workflows/terraform-plan.yml`** — triggers on PRs touching `infra/**`. Runs `fmt` → `init` → `validate` → `plan`, then posts the plan to the PR as a comment. Each step is `continue-on-error` so the comment always appears; a final step fails the job if anything broke.
- **`.github/workflows/terraform-apply.yml`** — triggers on push to `main` touching `infra/**`. Runs under `environment: production` (the gate) and does `terraform apply -auto-approve`.

Both pin Terraform to `1.9.8` — bump that later if you want a newer version.

---

## Step 5 — Commit and push

From the repo root:

```powershell
git add .github/workflows/terraform-plan.yml .github/workflows/terraform-apply.yml .gitignore infra/.terraform.lock.hcl docs/runbooks/08-terraform-cicd.md
git commit -m "ci: terraform plan-on-PR and gated apply-on-merge + runbook 08"
git push
```

> **Heads up:** this push touches `infra/.terraform.lock.hcl`, which matches the `infra/**` trigger — so it **immediately starts the `Terraform Apply` workflow**. That's expected, and it's your first live test of the gate (next step).

---

## Step 6 — Approve the first apply

1. Open the repo's **Actions** tab. You'll see a **Terraform Apply** run, **waiting**.
2. Click into it. There's a banner: **"Deployment review required"** → **Review deployments**.
3. Tick **production** → **Approve and deploy**.
4. The `terraform apply` step runs. Because nothing about the *infrastructure* changed (only workflow/lock files), it ends with **`Apply complete! Resources: 0 added, 0 changed, 0 destroyed.`**

That proves the apply pipeline: OIDC auth ✅, remote state access ✅, the approval gate ✅.

---

## Step 7 — Test the plan workflow with a real PR

Now exercise the PR path with a small, safe, free change — adding a tag.

```powershell
git checkout -b feat/ci-smoke-test
```

Edit `infra/locals.tf` — add one line inside the `common_tags` map:

```hcl
  common_tags = {
    project     = var.project_name
    environment = var.environment
    owner       = var.owner_email
    managed_by  = "terraform"
    cost_center = "portfolio"   # <-- add this line
  }
```

Then:

```powershell
git add infra/locals.tf
git commit -m "infra: tag resources with cost_center"
git push -u origin feat/ci-smoke-test
```

1. On GitHub, open a **Pull Request** from `feat/ci-smoke-test` into `main`.
2. Within a minute, **Terraform Plan** runs and posts a comment: `Terraform Plan — success`, with a collapsible plan showing **1 to change** (the Cosmos account gets the new tag).
3. **Merge** the PR.
4. The merge triggers **Terraform Apply** → approve it as in Step 6 → the tag is applied for real.

That's the whole loop working: PR → plan → review → merge → approve → apply.

---

## Step 8 — Final state checklist

- [ ] `medisync-deploy` has 3 federated credentials: `main` branch, `github-pull-request`, `github-env-production`.
- [ ] `medisync-deploy` has **Storage Blob Data Contributor** on `medisynctfstate2n3ccl`.
- [ ] GitHub `production` environment exists with **Required reviewers** = you.
- [ ] `terraform-plan.yml` posted a plan comment on the test PR.
- [ ] `terraform-apply.yml` paused for approval, then applied after you clicked Approve.
- [ ] `infra/.terraform.lock.hcl` is committed (visible on GitHub).
- [ ] The `cost_center` tag is live on the Cosmos account.

---

## What's next

Infrastructure foundation is **done** — identity, IaC, real resources, remote state, and a gated CI/CD pipeline. From here the project moves into **application code**: the `user`, `inventory`, and `match` Azure Functions, then the Next.js frontend. A couple more runbooks will appear later for console-heavy setup (Entra External ID auth, ACS Email domain verification), but the Terraform/infra runbook series ends here.

*(Optional hardening, anytime: repo → Settings → Branches → add a rule on `main` requiring the "terraform plan" status check to pass before merge.)*

---

## Troubleshooting

### Workflow fails: `AADSTS70021: No matching federated identity record found`
The OIDC token's subject doesn't match any federated credential. Check in **Entra ID → App registrations → medisync-deploy → Federated credentials** that the subjects are *exactly*:
- `repo:rizamgithub/medisync:pull_request`
- `repo:rizamgithub/medisync:environment:production`

Org/repo names are case-sensitive. Re-run `.temp/setup-cicd-azure.ps1` if one is missing.

### The apply ran without waiting for approval
The `production` environment has no protection rule, or wasn't created before the workflow ran (GitHub auto-creates an unprotected environment on first reference). Redo Step 2, then re-run the workflow.

### `terraform init` fails in CI: `Error: Failed to install provider` / checksum mismatch
The lock file is missing the Linux checksums. Locally run `terraform providers lock -platform=windows_amd64 -platform=linux_amd64` in `infra/`, commit the updated `.terraform.lock.hcl`, push.

### State error: `Error acquiring the state lock`
A previous run still holds the blob lease (or crashed holding it). Wait a few minutes. If it persists, the error prints a `Lock Info` block with an ID — break it with `terraform force-unlock <ID>` locally, after confirming no run is actually active.

### Plan workflow didn't run on the PR
The PR didn't change anything under `infra/**`, or the workflow file isn't on `main` yet. The plan workflow must be merged to `main` first (Step 5) before it runs on later PRs.

### Plan comment step fails with `403` / `Resource not accessible by integration`
`terraform-plan.yml` is missing `pull-requests: write` under `permissions`. It's set correctly in the committed file — check it wasn't edited out.

### CI fails on `terraform fmt`
Someone committed unformatted HCL. Run `terraform fmt` in `infra/` locally, commit the result.

---

## Related runbooks
- [[04-cicd-oidc]] — created `medisync-deploy` and proved the first OIDC handshake.
- [[07-remote-state-backend]] — the remote state this pipeline reads and writes.
