# Deploy Anutech Payroll to Render.com

The shortest path from this repo to a live URL — no Docker, no PowerShell, no servers to manage. Everything runs in your browser.

## What you'll have at the end

- A live backend at `https://anutech-backend.onrender.com`
- A live frontend at `https://anutech-frontend.onrender.com`
- A managed Postgres + Redis behind it
- Anutech demo tenant pre-seeded with all 8 employees
- Login working from any browser

## What you'll spend

**Free** for the demo (Render free tier). The catch:
- Backend cold-starts after 15 minutes of inactivity (~30 seconds to wake up)
- Free Postgres lasts 90 days, then you pay $7/mo or migrate
- Free Redis is unlimited

When you outgrow free tier, switch to **Starter** plan (~$7/mo per service) — same code, no changes needed.

---

## Step 1 — Get the API keys you'll need (5 minutes)

You'll paste these into Render in Step 4. Get them now so you don't break flow:

1. **Anthropic API key** (for AI agents)
   Visit [console.anthropic.com](https://console.anthropic.com) → Settings → API keys → "Create key" → copy the `sk-ant-...` string.

2. **(Optional) SMTP credentials** for payslip emails — Gmail App Password works:
   Google Account → Security → 2-Step Verification → App passwords → generate one for "Mail"

3. **(Optional) Zoho Books OAuth** — skip if you don't use Zoho yet.

---

## Step 2 — Push this repo to GitHub (5 minutes)

Render reads code from GitHub. So first you need a GitHub repo.

### If you don't have a GitHub account
Visit [github.com/signup](https://github.com/signup) → free account.

### Create the repo
1. Go to [github.com/new](https://github.com/new)
2. Repository name: `anutech-payroll`
3. Keep it **Private** (recommended — has business logic)
4. Do NOT check "Add README" (we already have one)
5. Click **Create repository**

GitHub will show "Quick setup" with a URL like `https://github.com/YOUR-USERNAME/anutech-payroll.git`. Copy it.

### Push from your machine
Open PowerShell in the project folder and run (replace `YOUR-USERNAME`):

```powershell
git remote add origin https://github.com/YOUR-USERNAME/anutech-payroll.git
git branch -M main
git push -u origin main
```

GitHub will ask you to sign in (it'll open a browser). After that, all 3 commits push up.

---

## Step 3 — Create a Render account (2 minutes)

1. Visit [dashboard.render.com/register](https://dashboard.render.com/register)
2. Sign up with **GitHub** (one-click — uses your new GitHub account)
3. When prompted, **authorize Render to access your GitHub repos**

---

## Step 4 — Deploy with the Blueprint (3 minutes)

The repo includes a `render.yaml` Blueprint that defines all 4 services (backend, frontend, postgres, redis).

1. In the Render dashboard, click **New +** → **Blueprint**
2. Connect the `anutech-payroll` repo
3. Render reads `render.yaml` and shows you the 4 services it'll create
4. Click **Apply** — Render starts provisioning

Takes ~5 minutes. You'll see logs streaming for each service.

---

## Step 5 — Set the secrets (3 minutes)

Some env vars are marked `sync: false` in the Blueprint — Render won't auto-fill them; you set them in the dashboard.

In Render → **anutech-backend** → **Environment**:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | The `sk-ant-...` key from Step 1 |
| `SEED_ADMIN_PASSWORD` | A strong password — this is your admin login password |
| `APP_BASE_DOMAIN` | `onrender.com` (or your custom domain later) |
| `CORS_ORIGINS` | `https://anutech-frontend.onrender.com` (the URL Render shows for the frontend service) |
| `SMTP_HOST` (optional) | e.g. `smtp.gmail.com` |
| `SMTP_USER` (optional) | your Gmail address |
| `SMTP_PASSWORD` (optional) | the App Password from Step 1 |

Click **Save changes** — Render redeploys automatically.

In Render → **anutech-frontend** → **Environment**:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://anutech-backend.onrender.com` |

Save → frontend redeploys.

---

## Step 6 — Open your app (30 seconds)

1. Click on **anutech-frontend** in the Render dashboard
2. Click the URL at the top (e.g. `https://anutech-frontend.onrender.com`)
3. You see the Anutech Payroll login screen
4. Sign in:
   - **Tenant slug:** `anutech`
   - **Email:** `pardeep@anutech.in`
   - **Password:** the `SEED_ADMIN_PASSWORD` you set in Step 5

You're in! Try:
- **Dashboard** — see 8 active employees pre-seeded
- **Payroll → Run payroll** for the previous month → 8 payslips generated, PF/ESI/PT/TDS computed
- **AI Chat** → ask *"What's the next PF deadline?"* → Claude routes to compliance agent
- **AI Chat** → ask *"Detect anomalies in last month's payroll"* → routes to payroll agent

---

## Updating the app

Push to GitHub. Render auto-deploys both services on every push to `main`:

```powershell
git add .
git commit -m "your change"
git push
```

---

## Common issues

### "Backend taking 30+ seconds to respond"
Free tier cold start. Upgrade to **Starter** ($7/mo) on the backend service for always-on.

### "Login fails — invalid credentials"
Did you set `SEED_ADMIN_PASSWORD` BEFORE first deploy? If not, the seed used a default. Check the backend logs in Render dashboard for the seed message. To reset: change `SEED_ADMIN_PASSWORD`, manually delete the existing employee row in Postgres (Render dashboard → database → Connect → run `DELETE FROM anutech.employees WHERE email='pardeep@anutech.in'`), restart backend.

### "AI Chat returns 'API key invalid'"
Check `ANTHROPIC_API_KEY` env var on the backend service. Make sure it starts with `sk-ant-` and has no spaces.

### "Frontend → backend CORS error in browser console"
Set `CORS_ORIGINS` on the backend to your exact frontend URL (no trailing slash). Restart backend.

### "Postgres connection refused"
Render's free Postgres takes 30-60 seconds to come up first time. Backend retries automatically — wait 1 minute and refresh.

---

## Custom domain (later)

When you're ready to use `payroll.anutech.in` instead of `*.onrender.com`:

1. In Render → frontend service → **Settings** → **Custom Domain** → add `payroll.anutech.in`
2. Render gives you a CNAME record. Add it to your DNS (your domain registrar).
3. For tenant subdomains (`*.payroll.anutech.in`), add a wildcard CNAME pointing at the same Render URL.
4. Update `APP_BASE_DOMAIN` and `CORS_ORIGINS` env vars on backend.
5. HTTPS provisioned automatically by Render.

---

## When you outgrow Render

The same Docker setup runs on:
- **DigitalOcean droplet** ($6/mo) — `git clone` + `docker-compose up`
- **AWS/GCP/Azure** — push images to ECR/GCR/ACR, deploy as containers
- **Your own VPS** — copy `docker-compose.yml`, set `.env`, run

The code doesn't change. Only the host does.
