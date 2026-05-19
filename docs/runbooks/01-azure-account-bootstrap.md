# Runbook 01 — Azure Account Bootstrap (Cost Safety)

> **Purpose:** Get a brand-new Azure account into a safe state where you can build MediSync without risking surprise bills. Do these steps **in order, before creating any other Azure resource**.
> **Estimated time:** 25–40 minutes (sign-up + identity verification can take 5–15 min on its own).
> **When to re-read:** Every time you create a new Azure account, or want to remind yourself why these guardrails exist.

---

## Why these steps exist

A Function in a retry loop, a forgotten Cosmos DB throughput unit, or a misconfigured Logic App can rack up real money fast. The guardrails below give you **two independent trip wires** before that happens:

1. **Cost Management budget** — three escalating alerts (50% / 80% / 100%) on a **$5 monthly cap**. Trajectory view.
2. **Spending limit** (Free Trial only) — Azure auto-suspends services when your $200 credit hits zero, so you literally cannot overspend during the trial period.

Both are **free**. Setting them up is not optional.

Azure differs from AWS in one important way: during the **Free Trial (first 30 days, $200 credit)**, Azure has a hard spending limit that suspends services at $0 remaining. When you upgrade to Pay-As-You-Go (PAYG) after 30 days, that limit **disappears** — at that point the budget alerts are your only protection.

---

## Pre-requisites (do these BEFORE starting)

- [ ] **Utility bill in your name** at your current address — open the PDF in another tab. Sign-up name + address must match it exactly.
  - Why: AWS suspended the previous account for an address mismatch with the landlord's utility bill. Don't repeat that.
- [ ] **Payment card** — credit or debit. Azure does a small auth charge (~MYR 4 or USD 1) to verify, refunded within days. Use a card with at least USD 5 headroom.
- [ ] **Mobile phone** — used for SMS verification during sign-up and for MFA later. Have it ready.
- [ ] **A clean browser profile** (or InPrivate / Incognito window) — avoids cookies from other Microsoft accounts conflicting.
- [ ] **Tenant name decided:** `medisyncrizam` (becomes `medisyncrizam.onmicrosoft.com` permanently).

---

## Step 1 — Create the Microsoft account

If you already have a personal Microsoft account (e.g. an Outlook/Hotmail/Xbox login), you can reuse it. Otherwise create a new one — recommended for cleanliness.

1. Open InPrivate window → go to **https://signup.live.com**.
2. **Use your real email** — `rizam3285@gmail.com` is fine. Microsoft will send a verification code there.
3. Set a strong unique password (save to password manager).
4. Enter your **legal name** as it appears on the utility bill.
5. Enter date of birth, country = **Malaysia**.
6. Verify the email with the 6-digit code.
7. Solve the captcha.

You now have a Microsoft account. Keep this tab open.

---

## Step 2 — Sign up for the Azure Free Account

1. New tab → **https://azure.microsoft.com/en-us/free**.
2. Click **Start free** (top right or center).
3. Sign in with the Microsoft account from Step 1.

### About you (Profile section)
4. **Country/Region:** Malaysia. *(This locks billing currency to MYR and tax rules — cannot be changed later. Confirm before continuing.)*
5. **First name / Last name:** exactly as on the utility bill.
6. **Email address for important Azure communications:** `rizam3285@gmail.com`.
7. **Phone:** your mobile, format `+60...`.
8. **Address:** street, city, state, postal code — **exactly as on the utility bill**.
9. Click **Next**.

### Identity verification by phone
10. Choose **Text me** → enter mobile → click **Send Message** → enter the 6-digit code.

### Identity verification by card
11. Enter card details. Confirm billing address matches the utility bill.
12. Tick the agreement boxes → click **Sign up**.

> ⚠️ If you see "We're unable to set up your free account" or any identity hold: **stop and ping me.** Don't retry repeatedly — Microsoft will flag the account. Common causes: VPN active, address mismatch, card declined the auth charge.

After successful sign-up, you'll land on **portal.azure.com** with a "Welcome to Azure" banner and **$200 credit valid for 30 days** shown in the top banner.

---

## Step 3 — Confirm your subscription and tenant

1. In Azure Portal, top search bar → type **Subscriptions** → click the result.
2. You should see one subscription named **"Azure subscription 1"** (or "Free Trial"). Click it.
3. **Copy these values into a safe note** (`.temp/azure-ids.md` after we git-init):
   - **Subscription ID** (GUID, e.g. `12345678-...`)
   - **Subscription name**
   - **Directory (Tenant) ID** (also a GUID, shown on the same page)
4. Top search bar → **Microsoft Entra ID** → click it.
5. On the Entra overview page, copy:
   - **Primary domain** (should be `<something>.onmicrosoft.com` — Microsoft auto-generated)
   - **Tenant ID** (confirm matches above)

> ℹ️ The auto-generated domain is ugly (e.g. `rizam3285gmail.onmicrosoft.com`). To get the clean `medisyncrizam.onmicrosoft.com`:
> - Entra ID → **Overview** → **Manage tenants** (or **Custom domain names**) → **Add custom domain**.
> - Enter `medisyncrizam.onmicrosoft.com` → if available, claim it and set as primary.
> - If taken, try `medisyncrizam01` etc.
> - Skip this step entirely if you're fine with the auto-generated name — it has no functional impact.

---

## Step 4 — Lock down the root identity with MFA

This is your equivalent of "AWS root MFA". The account you signed up with is now the **Global Administrator** of the new Entra tenant. If it's phished, the attacker owns everything.

### 4a — Enable Security Defaults (one-click MFA for all users)
1. **Microsoft Entra ID** → left sidebar → **Properties** (near bottom).
2. Scroll down → **Manage security defaults** link.
3. **Security defaults** → toggle to **Enabled** → tick "My organization is using Conditional Access" = **No** → **Save**.

> Security Defaults enforces MFA on all admin accounts, blocks legacy auth, and requires MFA registration within 14 days. It's free and the right baseline for a solo project.

### 4b — Register your MFA method
1. Sign out of Azure Portal.
2. Sign back in → Microsoft will prompt: **More information required** → click **Next**.
3. Install **Microsoft Authenticator** on your phone (App Store / Play Store) if you don't already have it.
4. In the browser: choose **Mobile app** → **Receive notifications for verification** → **Set up**.
5. In Microsoft Authenticator app → **+** → **Work or school account** → **Scan QR code** → scan the QR in browser.
6. Browser will send a test push → approve in app.
7. Add backup phone number (your mobile) as fallback.
8. Click **Done**.

From now on, every sign-in to Azure Portal requires an Authenticator approval. ✅

---

## Step 5 — Switch to USD billing view (optional but recommended)

Your billing currency is locked to MYR, but the **cost analysis views default to USD-equivalent**. This is actually helpful since all Azure pricing docs are in USD.

1. Top search → **Cost Management + Billing** → click it.
2. Left sidebar → **Cost Management** → **Cost analysis**.
3. Top-right of the chart → **gear icon** → confirm currency. If you see "Billing currency (MYR)", switch to **USD** for analysis.

---

## Step 6 — Create the production resource group

In Azure, every resource lives inside a **resource group** (logical container, like a folder). We'll create one now so all MediSync resources land in a single, easy-to-delete bucket.

1. Top search → **Resource groups** → click → **+ Create**.
2. **Subscription:** Azure subscription 1 (the only one).
3. **Resource group name:** `rg-medisync-prod`
4. **Region:** **Southeast Asia** (this is Singapore — lowest latency from Malaysia, supports all services MediSync needs).
5. Click **Review + create** → **Create**.

> ℹ️ The region you pick here is the *default* for resources created in this group, but each resource can override it. Southeast Asia is confirmed to support Azure Functions consumption plan, Cosmos DB serverless, Communication Services Email, and Entra External ID.

---

## Step 7 — Create the budget ($5 cap with escalating alerts)

This is your primary cost trip wire.

1. Top search → **Cost Management + Billing** → click.
2. Left sidebar → **Cost Management** → **Budgets** → **+ Add**.
3. **Scope:** if asked, pick **Subscription** (Azure subscription 1).
4. **Name:** `medisync-monthly-cap`
5. **Reset period:** Monthly
6. **Creation date:** today (default)
7. **Expiration date:** 2 years from today (or leave default)
8. **Amount:** `5` (in USD or MYR depending on display — keep it small)
9. Click **Next**.

### Alert conditions
10. Set three alert rows:

| Type | % | Amount | Action group |
|------|---|--------|--------------|
| Actual | 50 | $2.50 | (create new — see below) |
| Actual | 80 | $4.00 | (same action group) |
| Actual | 100 | $5.00 | (same action group) |

11. **Alert recipients (email):** `rizam3285@gmail.com` — comma-separated if more.
12. For each row, leave **Action group** blank for now (we'll create one in Step 8 and link back). Or, if the dialog requires it, click **Create action group** inline (Step 8 details apply).
13. Click **Create**.

---

## Step 8 — Create an Action Group for richer alerting (optional)

The budget already emails you. An Action Group lets you add SMS / webhook / Slack later without rebuilding the budget.

1. Top search → **Monitor** → left sidebar → **Alerts** → **Action groups** → **+ Create**.
2. **Subscription:** Azure subscription 1
3. **Resource group:** `rg-medisync-prod`
4. **Region:** Global
5. **Action group name:** `ag-medisync-billing`
6. **Display name:** `MediSync Billing` (12 chars max — used as SMS prefix)
7. **Next: Notifications**
8. Add a row: **Notification type** = Email/SMS/Push/Voice → **Name** = `email-rizam` → enter your email → tick **Email** → **OK**.
9. **Review + create** → **Create**.
10. Go back to **Budgets** → edit `medisync-monthly-cap` → attach `ag-medisync-billing` to each of the three alert thresholds → save.

---

## Step 9 — Verify the trip wires fire

You can't easily "test" a budget without actually spending, but you can verify the wiring:

1. **Cost Management → Budgets → medisync-monthly-cap** → confirm three alert rows visible.
2. **Monitor → Alerts → Action groups → ag-medisync-billing** → click → **Test action group** → pick "Budget" event type → **Test** → check your email inbox within 5 minutes.

If the test email arrives, all alerts are wired. ✅

---

## Step 10 — Final hardening (do today, not later)

- [ ] **Disable the spending limit auto-removal:** Cost Management → **Subscriptions** → your sub → **Manage** (or similar) → confirm "Spending limit" is **On** while in Free Trial. (Azure will prompt at trial-end to remove it; **do not remove it** until you're ready to commit to PAYG.)
- [ ] **Sign-in audit:** Entra ID → **Sign-in logs** → confirm only your own sign-ins.
- [ ] **Save IDs to `.temp/azure-ids.md`:** subscription ID, tenant ID, primary domain, resource group name. (Create `.temp/` if it doesn't exist; it's already in `.gitignore`.)

---

## What's next

✅ Account is bootstrapped and cost-safe. Next runbook: **`02-azure-rbac.md`** — create a `medisync-admin` service principal (replaces AWS IAM user) with a scoped role for daily CLI use, and a `medisync-deploy` SP wired to GitHub Actions via OIDC federated credentials.

---

## Troubleshooting

### "We're unable to set up your free account"
- VPN / proxy active → disable, try again.
- Card declined the auth charge → check with bank; some Malaysian debit cards block foreign auth charges.
- Address mismatch with card billing address → re-check, retry.
- Microsoft account already linked to a closed Azure trial → use a different Microsoft account.

### Sign-up succeeds but no $200 credit shown
- Make sure you signed up via **https://azure.microsoft.com/en-us/free** (the Free Account page), not a Pay-As-You-Go link. PAYG sign-ups do not get the $200 credit.

### Authenticator app push doesn't arrive
- App needs notification permission and an active internet connection.
- Fall back to "Use a verification code" (6-digit OTP shown in the app).

### Account suspended (don't panic)
- Microsoft email will state the reason. Most common: identity verification follow-up. Reply with the utility bill PDF as proof of address. Resolution typically 1–3 business days.
- If suspended: stop, ping me, do not retry creating another account from the same browser/IP.
