# Zoho Books integration — one-time setup

Goal: every payroll run pushes the total net salary as an Expense entry into your Zoho Books account, so accounting stays in sync without manual data entry.

This is a **one-time setup** (~10 min). After this, the **"Sync to Zoho"** button on each payroll run will work.

---

## What you'll end up with

Five environment variables added to your Render backend service:

| Variable | What it is |
|---|---|
| `ZOHO_CLIENT_ID` | OAuth app's client ID |
| `ZOHO_CLIENT_SECRET` | OAuth app's secret |
| `ZOHO_REFRESH_TOKEN` | Long-lived refresh token (one per Zoho org) |
| `ZOHO_ORGANIZATION_ID` | Your Zoho Books org's numeric id |
| `ZOHO_SALARIES_ACCOUNT_ID` | Expense account ID where salaries should land |
| `ZOHO_REGION` | `in` (default), `com`, `eu`, `com.au`, `jp`, `ca` |

---

## Step 1 — Create a Self Client in Zoho Developer Console

1. Open the **API Console** for your data center:
   - India: <https://api-console.zoho.in/>
   - US: <https://api-console.zoho.com/>
   - EU: <https://api-console.zoho.eu/>
   - (use whichever matches your Zoho Books region)

2. Click **"Self Client"** → **CREATE NOW**.
3. Tab **"Client Secret"** — copy:
   - **Client ID** → save as `ZOHO_CLIENT_ID`
   - **Client Secret** → save as `ZOHO_CLIENT_SECRET`

---

## Step 2 — Generate an authorization code

Still on the Self Client page:

1. Tab **"Generate Code"**
2. **Scope**: paste exactly:
   ```
   ZohoBooks.expenses.CREATE,ZohoBooks.settings.READ,ZohoBooks.chartofaccounts.READ
   ```
3. **Time Duration**: pick **10 minutes** (you only need it once)
4. **Scope Description**: anything, e.g. `payroll-sync`
5. Click **CREATE**
6. A modal pops up — click **CREATE** again to confirm
7. **Copy the code** that appears (looks like `1000.xxxxxxxxx`). It expires in 10 minutes — exchange it now.

---

## Step 3 — Exchange the code for a refresh token (one-time)

Open PowerShell/Terminal on your computer. Replace the placeholders and run (use the matching region URL — `accounts.zoho.in` for India):

**PowerShell:**
```powershell
$response = Invoke-RestMethod -Method Post `
  -Uri "https://accounts.zoho.in/oauth/v2/token" `
  -Body @{
    client_id = "PASTE_CLIENT_ID"
    client_secret = "PASTE_CLIENT_SECRET"
    code = "PASTE_AUTH_CODE_FROM_STEP_2"
    grant_type = "authorization_code"
  }
$response | ConvertTo-Json
```

**bash/curl:**
```bash
curl -s -X POST "https://accounts.zoho.in/oauth/v2/token" \
  -d "client_id=PASTE_CLIENT_ID" \
  -d "client_secret=PASTE_CLIENT_SECRET" \
  -d "code=PASTE_AUTH_CODE_FROM_STEP_2" \
  -d "grant_type=authorization_code"
```

You'll get back JSON like:
```json
{
  "access_token": "1000.xxx...",
  "refresh_token": "1000.yyy...",     ← THIS one. Save as ZOHO_REFRESH_TOKEN
  "api_domain": "https://www.zohoapis.in",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

Save the **refresh_token** (the long one ending with extra characters). The access_token expires in an hour — Anutech Payroll auto-refreshes it for you using the refresh token.

> **If you see `"error": "invalid_code"`** — the auth code expired (10 min). Go back to Step 2 and generate a fresh code.

---

## Step 4 — Find your Organization ID

In Zoho Books:

1. Top right → click your **profile picture** → **My Organizations**
2. Pick your org → in the URL you'll see something like `?organization_id=60024xxxxx`
3. Copy that number — save as `ZOHO_ORGANIZATION_ID`

OR — once env vars are partially set, open in a browser (after Render redeploy):
```
https://anutech-backend.onrender.com/api/v1/payroll/zoho-status
```
The response lists all orgs the connection has access to.

---

## Step 5 — Find/create the Salaries expense account

In Zoho Books:

1. Left sidebar → **Accountant** → **Chart of Accounts**
2. Filter by **Account Type: Expense**
3. If you already have a "Salaries" or "Salary Expense" account — click it
4. If not — **+ New** → Account Type: **Expense**, Name: **Salaries**, Save
5. The URL on the account detail page contains `account_id=460000000XXXXXX`
6. Save that number as `ZOHO_SALARIES_ACCOUNT_ID`

---

## Step 6 — Add all 6 vars to Render

1. Open <https://dashboard.render.com>
2. Click **anutech-backend** service
3. Left tab → **Environment**
4. Click **Add Environment Variable** for each:

| Key | Value |
|---|---|
| `ZOHO_CLIENT_ID` | from Step 1 |
| `ZOHO_CLIENT_SECRET` | from Step 1 |
| `ZOHO_REFRESH_TOKEN` | from Step 3 |
| `ZOHO_ORGANIZATION_ID` | from Step 4 |
| `ZOHO_SALARIES_ACCOUNT_ID` | from Step 5 |
| `ZOHO_REGION` | `in` (or your region) |

5. Click **Save Changes** — Render auto-redeploys (~5-7 min for backend)

---

## Step 7 — Verify

Once redeploy finishes, in your admin dashboard:

1. **Payroll** page → top of page shows a **Zoho Books** card → status should flip to **Connected** ✓
2. Each completed payroll run row gets a **"Sync to Zoho"** button next to "View payslips"
3. Click it for any run → green toast appears with the Zoho expense ID
4. In Zoho Books → **Purchases** → **Expenses** → you'll see the new entry with reference `payroll-run-<uuid>`

If something fails, the Zoho Books card on Payroll page shows the exact error.

---

## How re-syncing works

- Every click of "Sync to Zoho" creates a **new** expense entry in Zoho.
- The reference number is set to `payroll-run-<run_id>`, so duplicates are easy to spot in Zoho's expense list.
- If you accidentally double-sync, just delete the duplicate in Zoho directly.

---

## Per-tenant Zoho (advanced)

This v1 uses **one Zoho org for the entire Anutech installation**. If you go multi-tenant where each tenant has their own Zoho account, store credentials in the tenant DB instead of env vars. Code change required:

- Add a `tenant_settings` table with columns for the 5 Zoho fields
- Update `services/zoho_books.py:get_default_client()` to read from the request's tenant DB instead of env

Ping if you want this — it's a ~1-day change.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Card shows "Configured but connection failing: invalid_client" | Wrong client_id or secret | Re-copy from Self Client page |
| "invalid_code" when running Step 3 | Code expired (10 min) | Regenerate, exchange immediately |
| 403 on sync | Scope missing | Re-run Step 2 with the full scope string |
| Wrong region in URL | `ZOHO_REGION` wrong | Set to match your Zoho Books data center |
| "ZOHO_SALARIES_ACCOUNT_ID not set" | Step 5 not done | Add the env var |
| Zoho expenses appear with wrong amount | Pre-tax vs post-tax confusion | We sync `total_net` (after deductions). Switch to `total_gross` if you want pre-tax in Zoho. |
