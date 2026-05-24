# Runbook 10 — Entra External ID (Customer Auth)

> **Purpose:** Stand up a **customer-facing identity tenant** so MediSync users
> (Hospitals, Donors, Couriers, Doctors) can sign up and sign in, and so the
> three Function Apps can validate a real JWT instead of running `ANONYMOUS`.
>
> This creates a **separate Entra _External_ tenant** — distinct from your
> workforce tenant `rizamibrahimmygmail.onmicrosoft.com`. You register two apps
> in it: one **API** identity that all three Functions validate tokens against,
> and one **SPA** identity for the Next.js frontend. Then you build the
> sign-up/sign-in **user flow** that drives the hosted login experience.
>
> **Estimated time:** 60–75 minutes (tenant creation alone can take up to 30).
> **Prerequisite:** Runbook 01 complete. You have the subscription ID
> `4547eb5a-b286-4639-bcb7-2aa8a1fba2ea` and are **Global Admin** of the
> workforce tenant.
>
> **Cost:** $0/month. Entra External ID includes a permanent free tier of
> **50,000 monthly active users**. A portfolio project will never approach it.
> Linking to the subscription is for billing *identity* only — nothing is
> charged under 50k MAU.

> ⚠️ **This runbook produces no secrets.** The SPA is a *public client*
> (PKCE, no client secret); the APIs validate tokens offline against published
> signing keys (JWKS). There is nothing secret to leak — [[feedback-secret-leak-lesson]]
> still applies to the IDs you record, but none of them are credentials.

---

## Concepts (read once, then skip)

- **Workforce tenant** — `rizamibrahimmygmail.onmicrosoft.com`, the directory
  from runbook 01. Holds *your* admin identity and the Terraform/CI service
  principals. **Customers do not belong here.**
- **External tenant (CIAM)** — a second, separate directory built for
  *customer* identities. It has its own tenant ID, its own app registrations,
  its own users. "CIAM" = Customer Identity & Access Management.
- **User flow** — a configurable, Microsoft-hosted sign-up/sign-in journey.
  You pick the identity providers (email + password) and which attributes to
  collect; Microsoft renders and hosts the pages. No login UI to build.
- **API app registration** — represents your *backend*. It **exposes a scope**
  (e.g. `access_as_user`). A token minted for this app carries the app in its
  `aud` (audience) claim. All three Functions share **one** API registration.
- **SPA app registration** — represents your *frontend*. A **public client**:
  it authenticates with PKCE and never holds a secret. It is granted delegated
  permission to call the API's scope.
- **App ID URI** — the API's globally unique identifier, default
  `api://<api-client-id>`. The scope's full name is `<App ID URI>/access_as_user`.
- **`aud` / issuer / JWKS** — a Function validates a JWT by checking the
  signature against the tenant's **JWKS** (public signing keys), the **issuer**
  matches your external tenant, and **`aud`** matches the API app. All three
  values come from the tenant's OpenID discovery document.
- **Authority** — the base URL MSAL.js and the backend use to find all of the
  above: `https://<subdomain>.ciamlogin.com/`.

> **Scope of this runbook:** it ends with a working tenant, two app
> registrations, and a user flow. **Wiring MSAL.js into the frontend and JWT
> validation into the Functions is a separate follow-up** — see "What's next".

---

## Step 1 — Register the External ID resource provider

Creating an external tenant provisions an Azure resource, so the
`Microsoft.AzureActiveDirectory` provider must be registered on the
subscription. The CI service principal cannot self-register providers (the
lesson from runbook 06) — do it with your Global Admin account.

```powershell
az login
```
```powershell
az account set --subscription 4547eb5a-b286-4639-bcb7-2aa8a1fba2ea
```
```powershell
az provider register --namespace Microsoft.AzureActiveDirectory
```

Wait until it reports `Registered`:

```powershell
az provider show --namespace Microsoft.AzureActiveDirectory --query registrationState -o tsv
```

Do not continue until this prints `Registered` (takes a minute or two).

---

## Step 2 — Create the external tenant

1. Go to the **Microsoft Entra admin center** — <https://entra.microsoft.com> —
   signed in as your Global Admin account.
2. Left nav → **Entra ID** → **Overview** → **Manage tenants** tab.
3. Click **+ Create**.
4. Tenant type: select **External** → **Continue**.
5. **Deployment option:** choose **Use the Azure Subscription option**.

   > Microsoft also offers a free 30-day **trial tenant** with no subscription.
   > **Do not use it** — it expires and cannot be linked later. The
   > subscription-linked tenant is permanent and still $0 under 50k MAU.

6. **Basics tab:**
   - **Tenant name:** `MediSync Customers`
   - **Domain name:** `medisynccustomers` (must be globally unique; Azure
     appends `.onmicrosoft.com`. If taken, try `medisyncrizam`.)
   - **Location:** **Asia Pacific** (or the closest offered — this sets the
     data residency for customer accounts).
7. **Billing tab:** select subscription `Azure subscription 1`
   (`4547eb5a-b286-4639-bcb7-2aa8a1fba2ea`) and resource group
   `rg-medisync-prod`.
8. **Review + create** → **Create**.
9. Provisioning can take **up to 30 minutes**. Watch the **Notifications** bell.
10. When it finishes, **record into `.temp/azureid.md`** under a new
    `## Entra External ID` section:
    - **External tenant name:** `MediSync Customers`
    - **External tenant domain:** `<subdomain>.onmicrosoft.com`
    - **Tenant subdomain:** `<subdomain>` (the part before `.onmicrosoft.com`)
    - **External tenant ID:** `<GUID>` — **different** from the workforce
      tenant `382f042a-f53e-4419-aec8-cc4773f2169b`. Get it from
      **Manage tenants** → the new tenant's row, or its Overview page.

---

## Step 3 — Switch into the external tenant

**Every remaining step happens inside the external tenant**, not the workforce
tenant. This is the single most common mistake — app registrations made in the
wrong directory will not work.

1. In the Entra admin center, click the **Settings gear** (top right) →
   **Portal settings** → **Directories + subscriptions**. (Or click your
   account avatar → **Switch directory**.)
2. Find **MediSync Customers** in the list → click **Switch**.
3. Confirm the directory name shown under your avatar (top right) now reads
   **MediSync Customers**. If it still says the workforce tenant, you are in
   the wrong place — switch before continuing.

---

## Step 4 — Register the API app (`medisync-api`)

This one registration represents the whole backend; all three Functions
validate tokens against it.

1. **Entra ID** → **App registrations** → **+ New registration**.
2. **Name:** `medisync-api`
3. **Supported account types:** **Accounts in this organizational directory
   only** (single tenant — the external tenant).
4. **Redirect URI:** leave blank (an API has no login redirect).
5. **Register**.
6. On the Overview page, **record into `.temp/azureid.md`**:
   - **API application (client) ID:** `<GUID>`

### Expose a scope

7. Left sidebar → **Expose an API**.
8. Next to **Application ID URI**, click **Add** → accept the default
   `api://<api-client-id>` → **Save**.
9. Click **+ Add a scope**:
   - **Scope name:** `access_as_user`
   - **Who can consent:** **Admins and users**
   - **Admin consent display name:** `Access MediSync API`
   - **Admin consent description:** `Allows the app to call the MediSync API as the signed-in user.`
   - **State:** **Enabled**
   - **Add scope**.
10. **Record** into `.temp/azureid.md`:
    - **API App ID URI:** `api://<api-client-id>`
    - **Full scope:** `api://<api-client-id>/access_as_user`

### Add an optional claim (recommended)

11. Left sidebar → **Token configuration** → **+ Add optional claim** →
    token type **Access** → tick **`idtyp`** and **`email`** → **Add**. (If
    prompted to turn on the required Microsoft Graph permissions, accept.)
    These make the access token easier for the Functions to read.

---

## Step 5 — Register the SPA app (`medisync-spa`)

This represents the Next.js frontend — a public client.

1. **App registrations** → **+ New registration**.
2. **Name:** `medisync-spa`
3. **Supported account types:** **Accounts in this organizational directory
   only**.
4. **Redirect URI:** platform dropdown → **Single-page application (SPA)** →
   value `http://localhost:3000`.
5. **Register**.
6. On the Overview page, **record into `.temp/azureid.md`**:
   - **SPA application (client) ID:** `<GUID>`
7. Left sidebar → **Authentication**. Under the **Single-page application**
   platform, click **Add URI** and add the deployed frontend origin once it
   exists, e.g. `https://<your-static-web-app>.azurestaticapps.net`. (You can
   return and add this after the frontend is deployed.)
   - Confirm **no client secret** exists under **Certificates & secrets** — a
     SPA must stay a public client. Leave it empty.

> Redirect URIs are **origins only** for a SPA (no path), and MSAL.js handles
> the rest. `trailingSlash` is irrelevant here.

---

## Step 6 — Grant the SPA permission to call the API

1. Still in **`medisync-spa`** → left sidebar → **API permissions**.
2. **+ Add a permission** → **My APIs** tab → select **`medisync-api`**.
3. **Delegated permissions** → tick **`access_as_user`** → **Add permissions**.
4. Back on the API permissions list, click **Grant admin consent for
   MediSync Customers** → **Yes**.
5. Confirm the `access_as_user` row shows **Status = Granted**. You may remove
   the default `User.Read` Microsoft Graph permission — MediSync does not call
   Graph — but leaving it is harmless.

---

## Step 7 — Create the sign-up / sign-in user flow

1. **Entra ID** → **External Identities** → **User flows** → **+ New user flow**.
2. **Name:** `medisync-signupsignin` (the portal prefixes it, so the final
   name may appear as `B2X_1_medisync-signupsignin` or similar — fine).
3. **Identity providers:** tick **Email with password**.

   > "Email one-time passcode" is the passwordless alternative — also $0.
   > Password keeps the demo predictable for an interview walkthrough.

4. **User attributes:** under **Collect attribute**, tick **Email Address**,
   **Display Name**, and **Given Name** / **Surname** as you like. The
   application-specific MediSync role (Hospital/Donor/etc.) is **not** an Entra
   attribute — it lives in the `profiles` Cosmos container and is set by the
   user service's `POST /api/auth/signup`. Keep the flow minimal.
5. **Create**.

### Associate the SPA with the flow

6. Open the new user flow → left sidebar → **Applications** → **+ Add
   application** → select **`medisync-spa`** → **Select**.

   > The **API** app is *not* added to a user flow — only apps that initiate
   > login (the SPA) are. The API only ever *validates* the resulting token.

---

## Step 8 — Record the authority, issuer & JWKS

The frontend (MSAL.js) and the Functions (JWT validation) need these. Fetch
the discovery document so you copy exact values rather than guessing.

1. Build the OpenID discovery URL (substitute *your* subdomain and external
   tenant ID):
   ```
   https://<subdomain>.ciamlogin.com/<external-tenant-id>/v2.0/.well-known/openid-configuration
   ```
2. Open it in a browser, or:
   ```powershell
   curl https://<subdomain>.ciamlogin.com/<external-tenant-id>/v2.0/.well-known/openid-configuration
   ```
3. From the JSON, **record into `.temp/azureid.md`**:
   - **Authority** (for MSAL.js): `https://<subdomain>.ciamlogin.com/`
   - **`issuer`** — copy verbatim (the Functions check the `iss` claim against
     this).
   - **`jwks_uri`** — copy verbatim (the Functions fetch signing keys here).
   - **Expected `aud`**: the **API application (client) ID** from Step 4.

Your `## Entra External ID` section of `.temp/azureid.md` should now hold:
external tenant name / domain / subdomain / ID, API client ID, API App ID URI,
full scope, SPA client ID, user flow name, authority, issuer, jwks_uri.

---

## Step 9 — Final state checklist

- [ ] `Microsoft.AzureActiveDirectory` provider registered on the subscription.
- [ ] External tenant **MediSync Customers** created, subscription-linked, and
      its tenant ID recorded (distinct from the workforce tenant).
- [ ] `medisync-api` registered **in the external tenant**, with App ID URI set
      and the `access_as_user` scope **Enabled**.
- [ ] `medisync-spa` registered as a **SPA public client** (redirect
      `http://localhost:3000`, **no** client secret).
- [ ] `medisync-spa` has delegated `access_as_user` on `medisync-api` with
      **admin consent granted**.
- [ ] User flow `medisync-signupsignin` created and `medisync-spa` added to it.
- [ ] `.temp/azureid.md` holds all IDs, the authority, issuer, and jwks_uri.

---

## What's next

This runbook delivers the **identity infrastructure**. Two wiring tasks remain,
each a separate piece of work:

1. **Frontend MSAL.js integration** — add `@azure/msal-browser` /
   `@azure/msal-react` to `frontend/`, configure it from
   `NEXT_PUBLIC_*` env vars (authority, SPA client ID, the API scope), and
   replace the `auth.ts` stub (`TODO(entra)`). Sign-in then yields an access
   token the `api.ts` client attaches as `Authorization: Bearer`.
2. **Backend JWT validation** — in each service, replace
   `http_auth_level=ANONYMOUS` / the `TODO(entra)` in `routes.py` with a token
   validator that checks signature (JWKS), `iss` (issuer), and `aud` (the API
   client ID). The shared `packages/shared/medisync_shared` package is the
   natural home for that validator so all three services reuse it.

Those two tasks consume the values recorded in Step 8 — they do **not** need
any further console work in Entra.

---

## Troubleshooting

### "Insufficient privileges" creating the external tenant
You need at least the **Tenant Creator** role in the workforce tenant; Global
Admin includes it. Also confirm Step 1's provider registration finished.

### App registration doesn't appear / "My APIs" is empty in Step 6
You registered the app in the **workforce tenant** by mistake. Check the
directory name under your avatar reads **MediSync Customers** (Step 3), and
re-create the registration in the external tenant.

### Tenant creation stuck "in progress" past 30 minutes
Refresh **Manage tenants**. If it still hasn't appeared after ~45 minutes,
check the Azure portal **Activity log** on the subscription for a failure —
usually the `Microsoft.AzureActiveDirectory` provider was not registered first.

### `ciamlogin.com` discovery URL returns 404
The subdomain or tenant ID is wrong. The subdomain is the part **before**
`.onmicrosoft.com` in the tenant domain. The tenant ID must be the **external**
tenant's GUID, not the workforce tenant's.

### Admin consent button greyed out / "Grant admin consent" missing
You must be an admin **in the external tenant**. The account that created the
tenant is its Global Admin — make sure you switched into it (Step 3) and
aren't viewing as a guest.

### Token's `aud` doesn't match when the backend validates it
A token minted for the SPA calling the API carries `aud` = the **API** client
ID (or its App ID URI), **not** the SPA client ID. The Functions must expect
the `medisync-api` client ID. If `aud` looks like `00000003-0000-0000-...`
(Microsoft Graph), the frontend requested the wrong scope — it must request
`api://<api-client-id>/access_as_user`, not `User.Read`.
