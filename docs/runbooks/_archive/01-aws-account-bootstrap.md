# Runbook 01 — AWS Account Bootstrap (Cost Safety)

> **Purpose:** Get a brand-new AWS account into a safe state where you can build MediSync without risking surprise bills. Do these steps **in order, before creating any other AWS resource**.
> **Estimated time:** 15–20 minutes (after AWS finishes account activation, which can take up to 24 hours).
> **When to re-read:** Every time you create a new AWS account, or want to remind yourself why these guardrails exist.

---

## Why these steps exist

A misconfigured Lambda in a retry loop, a forgotten RDS instance, or a Cognito flow gone wrong can rack up tens to hundreds of dollars in a day. The guardrails below give you **two independent trip wires** before that happens:

1. **CloudWatch billing alarm** — fires once when estimated charges cross **$1 USD**. First-line trip wire.
2. **AWS Budget** — three escalating alerts (50% / 80% / 100%) on a **$5 monthly cap**. Trajectory view, not just one-off alarm.

Both are **free**. Setting them up is not optional.

---

## Pre-requisites (already done if you're reading this)

- [x] AWS account created, root user has MFA enabled.
- [x] $1 identity-verification hold confirmed by your bank (refunded in 3–5 days).
- [x] Account activation complete — you can open Lambda / DynamoDB in the AWS Console without "data couldn't be retrieved" errors.

---

## Step 1 — Enable billing metrics publication (one-time)

CloudWatch only publishes billing metrics if you opt in. Without this, the Billing tile won't appear in the alarm wizard.

1. **Top-right of AWS console** → click your account name → **Billing and Cost Management**.
2. Left sidebar → **Billing preferences**.
3. Find the **"Alert preferences"** section → click **Edit**.
4. Tick both boxes:
   - ☑ Receive AWS Free Tier alerts (with your email)
   - ☑ Receive CloudWatch billing alerts
5. Click **Update** / **Save**.
6. Wait ~15 minutes for the first billing metric to publish.

---

## Step 2 — Switch to N. Virginia (us-east-1)

**Billing metrics only exist in `us-east-1`**, regardless of where your services run. Every billing alarm must be created in this region.

1. Top-right region switcher → **US East (N. Virginia) us-east-1**.

---

## Step 3 — Create the $1 billing alarm

1. **Search bar** → "CloudWatch" → open CloudWatch.
2. Left sidebar → **Alarms** → **All alarms** → orange **Create alarm**.
3. **Select metric** → tile **Billing** → **Total Estimated Charge** *(not "By Service")* → tick the row `USD / EstimatedCharges` → orange **Select metric**.
4. **Specify metric and conditions:**
   - Statistic: `Maximum`
   - Period: `6 hours` *(billing data only updates every few hours; shorter periods give no benefit)*
   - Threshold type: `Static`
   - Whenever EstimatedCharges is: `Greater >` than `1` *(= $1 USD)*
   - **Next**
5. **Configure actions:**
   - Alarm state trigger: `In alarm`
   - SNS topic: **Create new topic**
     - Topic name: `medisync-billing-alerts`
     - Email endpoints: your email
   - Click **Create topic** *(important — without this the topic isn't created)*
   - **Next**
6. **Add alarm details:**
   - Alarm name: `medisync-billing-alarm-1usd`
   - Description (optional but useful): `Alerts when estimated AWS charges exceed $1 USD.`
   - **Next** → **Create alarm**.

7. **Confirm the SNS subscription:**
   - Check email inbox (and spam) for `AWS Notification - Subscription Confirmation` from `no-reply@sns.amazonaws.com`.
   - Click **Confirm subscription** link.
   - Without this step, the alarm fires but no email arrives.

✅ Alarm is now armed.

---

## Step 4 — Create the $5 Budget (multi-threshold)

The Budget is **free** for the first 2 budgets per account. We only need 1.

1. Top-right → account name → **Billing and Cost Management**.
2. Left sidebar → **Budgets** → orange **Create budget**.
3. Budget setup:
   - Choose **Customize (advanced)**.
   - Budget type: **Cost budget — Recommended**.
   - **Next**.
4. Set amount:
   - Budget name: `medisync-monthly-cap`
   - Period: `Monthly`
   - Renewal type: `Recurring budget`
   - Start month: current month
   - Method: `Fixed`
   - Amount: `5.00` (USD)
   - Scope: `All AWS services` (default)
   - **Next**.
5. Add three alert thresholds — all email-only:

   | # | Threshold | Of | Trigger | Email |
   |---|-----------|----|---------|-------|
   | 1 | 50 | % of budgeted amount | Actual | your email |
   | 2 | 80 | % of budgeted amount | Actual | your email |
   | 3 | 100 | % of budgeted amount | Actual | your email |

   Click **Next**.
6. **Attach actions** → **Skip** (just click **Next** — we don't want auto-stop actions yet).
7. **Review** → **Create budget**.

Budget alerts do **not** require email confirmation. They fire immediately when triggered.

✅ Budget is now armed.

---

## Step 5 — Enable Cost Explorer

Needed so the AWS Cost Explorer MCP server (used by Claude Code) can query spend, and so you can see daily cost breakdowns.

1. Top-right → account name → **Billing and Cost Management**.
2. Left sidebar → **Cost Explorer**.
3. On modern AWS accounts, simply **visiting the page enables it automatically** — you'll see *"Since this is your first visit, it will take some time to prepare your cost and usage data. Please check back in 24 hours."* That message confirms enablement. *(Older accounts may show an explicit "Enable Cost Explorer" button — click it if present.)*
4. First report data takes ~24 hours to populate. This does not block anything else.

✅ Cost Explorer enabled.

---

## Verification checklist

After all steps:

- [ ] In CloudWatch (us-east-1) → Alarms → you see `medisync-billing-alarm-1usd`, state `Insufficient data` *(normal until first billing datapoint)*.
- [ ] In Budgets → you see `medisync-monthly-cap` with $0 spent / $5 budgeted.
- [ ] In your email → you have a confirmation receipt from SNS for the alarm topic subscription.
- [ ] In Cost Explorer → page loads (data may be empty for first 24h).

---

## What happens if I trip a wire?

- **$1 alarm trips:** Email arrives with subject containing `ALARM: medisync-billing-alarm-1usd`. **Action:** Log in immediately, go to Cost Explorer, identify which service is charging. Run `terraform destroy` on the offender or fix the misconfiguration.
- **Budget 50%/80%/100% triggers:** Email arrives. **Action:** Investigate trajectory in Cost Explorer. Consider tearing down if not urgently needed.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Billing" tile missing in metric picker | Billing alerts not enabled, OR wrong region | Re-do Step 1; confirm region = us-east-1 |
| "No data available" graph during alarm setup | New account, no billing data yet | Normal — alarm still works once data flows (~24h) |
| Alarm fires but no email | Skipped SNS subscription confirmation | Find the confirmation email, click the link |
| "Total Estimated Charge" tile missing | Drilled too deep into Billing > By Service | Click `Billing` in breadcrumb to back up |
| Singapore console "data couldn't be retrieved" | Account still activating | Wait up to 24h; usually 1–4h |
| "Authentication failed because your account has been suspended" within hours of signup | AWS automated fraud/identity-verification flag — common for new accounts. **NOT caused by your usage**. | (1) Check email + spam for AWS verification request — usually asks for photo ID upload. (2) If no email, open AWS Support case via the "Contact Us" link on the suspended page → "Account and Billing Support" → "Reactivation." (3) Do NOT click "Payments" — you owe nothing; paying won't fix an identity suspension. (4) Do NOT create a second account with the same details — strengthens the fraud flag. (5) Typical resolution 1–7 business days. |
| "The security token included in the request is invalid" appears repeatedly even after re-login | May precede a full account suspension. Check sign-in to see if the account is in a degraded state. | If you can't sign back in cleanly, see the suspension row above. |

---

## Related runbooks

- `02-iam-users.md` — create `medisync-admin` and `medisync-mcp` users with scoped policies *(next)*
- `03-terraform-bootstrap.md` — S3 state bucket + DynamoDB lock table + GitHub OIDC role *(M0)*
