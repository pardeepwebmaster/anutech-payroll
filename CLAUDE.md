# Anutech Payroll — Engineering Guide

> **This file is read by every Claude session before any work. Treat it as the source of truth for architecture, conventions, and workflows.**

## Product

**Anutech Payroll** — multi-tenant SaaS payroll for Indian companies.
- Made by: Anutech (IT company, India)
- Domain: `payroll.anutech.in` (subdomain-per-tenant: `{tenant}.payroll.anutech.in`)

## Stack

- **Backend**: Python 3.11, FastAPI 0.115, SQLAlchemy 2.0, Alembic, Pydantic v2 (`pydantic-settings`)
- **DB**: PostgreSQL 15 (schema-per-tenant isolation, `pgcrypto` for `gen_random_uuid()`)
- **Cache/Queue**: Redis 7
- **Background jobs**: APScheduler (in-process, IST cron)
- **AI**: Anthropic Claude API (`anthropic` SDK), default model `claude-opus-4-7`
- **PDF**: WeasyPrint (Jinja2 HTML template → PDF)
- **Frontend**: React 18 + Vite 6 + TailwindCSS 3 + react-router-dom 6 + axios
- **Infra**: Docker Compose locally, nginx reverse proxy, Render Blueprint (`render.yaml`) for cloud

## Multi-tenancy: schema-per-tenant

This is the **central architectural rule**. Get it wrong and tenants leak data.

1. **Master DB schema** (`public`) holds `tenants`, `subscription_plans`, `billing`. No tenant data here.
2. **Each tenant gets its own PostgreSQL schema** named after their slug (e.g. `anutech`).
3. **Every authenticated request** passes through `TenantMiddleware` (`backend/core/tenant_middleware.py`), which:
   - Decodes the JWT (when present) to get `tenant_schema`, `user_id`, `role`
   - Stores them on `request.state` for downstream dependencies
4. The `get_tenant_session` FastAPI dependency (`backend/core/database.py`) opens a session and runs `SET search_path TO "{tenant_schema}", public` before yielding.
5. **Every router query** must depend on `get_tenant_session` (or `get_master_session` for master-DB endpoints) — never construct a session that bypasses the middleware.
6. **Tenant onboarding** = create schema + run `migrations/tenant_schema.sql` DDL + insert admin user. See `auth.register_tenant`.
7. **Subdomain routing**: nginx maps `{tenant}.payroll.anutech.in` → backend with `X-Tenant-Slug` header (informational, used at login; JWT carries tenant after).

**Public paths** that skip auth (defined in `tenant_middleware.PUBLIC_PATH_PREFIXES`): `/api/v1/auth/login`, `/api/v1/auth/register`, `/api/v1/auth/forgot-password`, `/api/v1/auth/reset-password`, `/api/v1/health`, `/docs`, `/redoc`, `/openapi.json`.

**Non-negotiable test**: a tenant's JWT must NEVER read another tenant's rows. The integration test at `tests/test_tenant_isolation.py` enforces this and is required to pass before any merge. **It hits a real PostgreSQL** — no SQLite shortcut.

## Project layout

```
anutech-payroll/
├── backend/
│   ├── main.py                       # FastAPI entry, lifespan (auto-init + scheduler), router wiring
│   ├── Dockerfile                    # python:3.11-slim + WeasyPrint deps; PYTHONPATH=/app
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                      # versioned migrations (versions/ currently empty)
│   ├── core/
│   │   ├── config.py                 # Pydantic Settings; AUTO_INIT_DB / AUTO_SEED_TENANT toggles
│   │   ├── database.py               # Engine + session factory + tenant schema helpers
│   │   ├── tenant_middleware.py      # JWT → request.state.{tenant_schema,user_id,role}
│   │   └── security.py               # JWT, bcrypt, get_current_user / require_admin
│   ├── models/
│   │   ├── master_models.py          # Tenant, SubscriptionPlan, Billing (schema=public)
│   │   └── tenant_models.py          # Employee, PayrollRun, Payslip, Leave, ComplianceFiling, AgentLog
│   ├── routers/
│   │   ├── auth.py                   # register tenant, login, /me
│   │   ├── employees.py              # CRUD with tenant scope, search/filter, CSV export
│   │   ├── payroll.py                # run-payroll, payslips list/get, PDF download, Zoho sync
│   │   ├── leaves.py                 # apply, list, decide, my-balance, pending-count
│   │   ├── compliance.py             # PF/ESI/TDS/PT filing tracker
│   │   ├── reports.py                # salary + compliance reports
│   │   └── ai_chat.py                # proxies to agents.orchestrator + lists agents/logs
│   ├── services/
│   │   ├── payroll_calculator.py     # Indian payroll engine — canonical, do not duplicate
│   │   ├── zoho_books.py             # Zoho OAuth refresh + create_expense
│   │   ├── email_service.py          # WeasyPrint payslip PDF + SMTP send
│   │   └── scheduler.py              # APScheduler IST cron jobs
│   ├── agents/
│   │   ├── __init__.py               # BaseAgent ABC + AgentContext + Anthropic client (FROZEN contract)
│   │   ├── orchestrator.py           # keyword routing → LLM-fallback classifier → specialist
│   │   ├── hr_agent.py               # HR (employees, leaves)
│   │   ├── payroll_agent.py          # payroll calculation, anomaly detection
│   │   ├── finance_agent.py          # Zoho Books, expense reports, salary aggregates
│   │   └── compliance_agent.py       # PF/ESI/TDS/PT deadlines
│   ├── migrations/
│   │   ├── master_schema.sql         # DDL for master DB + seeds the 3 plans
│   │   └── tenant_schema.sql         # DDL template for new tenant
│   └── scripts/
│       └── seed_first_tenant.py      # idempotent seed of Anutech tenant + 8 employees
├── frontend/
│   ├── package.json                  # vite, react 18, axios, react-router-dom
│   ├── vite.config.js                # dev proxy /api → http://localhost:8000
│   ├── tailwind.config.js            # primary palette = Anutech purple #7F77DD
│   ├── postcss.config.js
│   ├── index.html
│   ├── Dockerfile
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                   # routes: /login, /register, /admin/*, /me/*
│       ├── index.css
│       ├── lib/                      # api.js (axios + JWT), auth.jsx (AuthProvider), format.js
│       ├── components/               # AdminLayout, EmployeeLayout, DataTable
│       └── pages/
│           ├── Login.jsx
│           ├── Register.jsx
│           ├── admin/                # Dashboard, Employees, RunPayroll, Leaves, Compliance, Reports, AIChat
│           └── employee/             # MyPayslips, LeaveApply, MyProfile
├── tests/
│   ├── conftest.py                   # fixtures: master DB once, throwaway tenant schema per test
│   ├── test_payroll_calculator.py
│   └── test_tenant_isolation.py      # multi-tenant isolation invariant
├── docker-compose.yml                # postgres + redis + backend + frontend + nginx
├── nginx.conf                        # subdomain → X-Tenant-Slug + proxy to backend/frontend
├── render.yaml                       # Render Blueprint (Postgres + Redis + backend + frontend static)
├── .env.example
├── README.md
├── DEPLOY.md                         # step-by-step Render deployment
├── ZOHO_SETUP.md                     # one-time OAuth setup for Zoho Books
└── iframe-test.html                  # standalone embed-test harness
```

## Frozen contracts (don't mutate without lead approval)

- `backend/agents/__init__.py:BaseAgent` — orchestrator and `ai_chat` router both depend on it.
- `backend/core/database.py:get_tenant_session` — every router uses this dependency.
- `backend/core/security.py:get_current_user` / `require_admin` — single source of auth.
- `backend/models/*.py` — schema changes require an Alembic migration **and** matching edits to `migrations/tenant_schema.sql` (raw SQL is what onboarding runs).

## Indian payroll calculation (canonical)

`backend/services/payroll_calculator.py:calculate_payslip` is the single source of truth. Anyone displaying a payslip must call this — never re-implement.

Given a `gross` monthly salary:
```
basic              = gross * 0.40
hra                = basic * 0.40
special_allowance  = gross - basic - hra

# Provident Fund
pf_employee   = basic * 0.12 if basic > 0 else 0
pf_employer   = basic * 0.12

# Employee State Insurance — only if gross <= 21000
esi_employee  = gross * 0.0075 if gross <= 21000 else 0
esi_employer  = gross * 0.0325 if gross <= 21000 else 0

# Professional Tax (Maharashtra default, configurable)
pt            = 200

# Tax Deducted at Source — annual income tax slab, divided by 12
tds           = compute_monthly_tds(annual_gross)

net_pay       = gross - pf_employee - esi_employee - pt - tds
```

**TDS slabs (FY 2024-25 / 2025-26 — New Regime, default in `payroll_calculator.py`)**:
standard deduction ₹75,000; slabs 0–3L 0%, 3–7L 5%, 7–10L 10%, 10–12L 15%, 12–15L 20%, >15L 30%; 4% Health & Education Cess on the tax.

**Rounding**: amounts use `Decimal` and quantise to 2 decimals with `ROUND_HALF_UP`. DB columns are `Numeric(12, 2)` (`Numeric(14, 2)` for run totals).

## Conventions

### Python
- `from __future__ import annotations` at the top of every module.
- Type hints everywhere; Pydantic v2 schemas; SQLAlchemy 2.x style (`Mapped`, `mapped_column`).
- FastAPI handlers can be sync (psycopg2 is sync). Use `Depends(get_tenant_session)` — don't open sessions yourself inside routers.
- Errors: raise `HTTPException` with explicit status codes. Don't return error dicts.
- Logging: `import logging; log = logging.getLogger(__name__)` — no `print`.
- One file = one responsibility. Don't merge routers.

### Naming
- Routes: `/api/v1/<resource>` (kebab when multi-word).
- DB tables: snake_case plural (`employees`, `payroll_runs`).
- Pydantic schemas: `EmployeeCreate`, `EmployeeRead`, `EmployeeUpdate`.
- Tests: `test_<module>_<behavior>`.

### Frontend
- React 18 with hooks; **no class components**.
- Filenames: `PascalCase.jsx` for components, `camelCase.js` for utilities.
- Tailwind utility classes; theme color is **`#7F77DD`** (Anutech purple) — defined as `primary` in `tailwind.config.js`.
- API calls go through `src/lib/api.js` (axios instance with JWT interceptor + 401 → `/login` redirect). Use `downloadFile(path, filename)` for binary downloads (PDF, CSV).
- Auth state lives in `src/lib/auth.jsx` (`AuthProvider`, `useAuth`). Token stored as `localStorage["anutech.token"]`.
- Tables use the shared `<DataTable>` component (search + filter + CSV/PDF export hooks).
- Vite dev server proxies `/api` to `http://localhost:8000`. In prod, set `VITE_API_URL` to the deployed backend.

### Git
- One commit per logical change. Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).
- Never commit `.env`, `*.db`, `node_modules`, `__pycache__`, `frontend/dist/`.
- Run `pytest tests/ -v` before committing changes that touch backend code.

## Auth & request flow

1. User calls `POST /api/v1/auth/login` with `{slug, email, password}`.
2. `auth.login` opens a master session, finds the tenant by slug, then opens a tenant session and looks up the user by email (in the tenant's `employees` table).
3. On success, `create_access_token(user_id, tenant_schema, role)` issues a JWT.
4. Frontend stores it in `localStorage` and sends `Authorization: Bearer ...` on every request (axios interceptor).
5. `TenantMiddleware` decodes the JWT and pins `tenant_schema` to `request.state`.
6. Routers depend on `get_tenant_session` → SET search_path → ORM queries operate inside the tenant schema.
7. `get_current_user` re-verifies the token and returns a `CurrentUser`. Use `require_admin` to gate admin-only endpoints.

## App lifespan & auto-bootstrap

`backend/main.py` registers a FastAPI lifespan hook that, on startup:
- If `AUTO_INIT_DB=true`: runs `migrations/master_schema.sql` (idempotent — safe to re-run).
- If `AUTO_SEED_TENANT=true`: imports `scripts.seed_first_tenant` and ensures the Anutech demo tenant + employees.
- If `APP_ENV != "test"`: starts APScheduler.

Both auto-bootstrap toggles default to `false` for local dev (use the explicit `seed_first_tenant` command). They are set to `true` in `render.yaml` so a fresh Render deploy boots into a usable state.

## Environment variables

All defined in `.env.example`. Required for backend boot:
- `DATABASE_URL` — `postgresql+psycopg2://...` (plain `postgres://` URLs are auto-normalised)
- `MASTER_SCHEMA` — usually `public`
- `JWT_SECRET` — long random string
- `JWT_ALGORITHM` — `HS256`
- `JWT_EXPIRES_MINUTES` — `1440`
- `ANTHROPIC_API_KEY` — for AI agents (empty disables agent calls)
- `ANTHROPIC_MODEL` — model id (default `claude-opus-4-7`)
- `REDIS_URL` — `redis://redis:6379/0`
- `APP_ENV` — `dev` | `prod` | `test`
- `LOG_LEVEL` — `INFO` | `DEBUG`
- `APP_BASE_DOMAIN` — `payroll.anutech.in`
- `CORS_ORIGINS` — comma-separated extra origins (used in prod)
- `AUTO_INIT_DB`, `AUTO_SEED_TENANT` — bool, default false
- `DEFAULT_PROFESSIONAL_TAX` (default 200), `ESI_GROSS_THRESHOLD` (default 21000)

Optional integrations (skipped if blank):
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
- `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`, `ZOHO_ORGANIZATION_ID`, `ZOHO_SALARIES_ACCOUNT_ID`, `ZOHO_REGION` (default `in`) — see `ZOHO_SETUP.md`

Seed-only (read by `scripts/seed_first_tenant.py`):
- `SEED_ADMIN_EMAIL` (default `pardeep@anutech.in`), `SEED_ADMIN_PASSWORD` (default `ChangeMe123!`)

## Subscription plans (seeded by `master_schema.sql`)

| Plan    | Price/month | Max employees | Features         |
|---------|-------------|----------------|------------------|
| Starter | ₹1,999      | 10             | basic            |
| Growth  | ₹4,999      | 25             | + AI agents      |
| Scale   | ₹8,999      | 50             | + all + priority |

## First tenant seed (Anutech demo)

- **Slug**: `anutech` → schema `anutech` → `anutech.payroll.anutech.in`
- **Plan**: Scale
- **Employees** (₹ monthly gross):

| Name           | Role                  | Department  | Gross    |
|----------------|-----------------------|-------------|----------|
| Pardeep Sharma | Director + Sales Head | Leadership  | 1,80,000 |
| Abhishek       | CTO                   | Engineering | 35,000   |
| Hitesh Baghel  | COO + HR              | Operations  | 52,000   |
| Pawan          | Developer             | Engineering | 24,000   |
| Ananya Sharma  | Sales Executive       | Sales       | 90,000   |
| Darshan Kumar  | Marketing Executive   | Sales       | 20,000   |
| Ranjeet Raj    | Support               | Operations  | 38,000   |
| Mayank Sharma  | Accounts              | Accounts    | 80,000   |

Run inside the backend container:
```bash
docker-compose exec backend python -m backend.scripts.seed_first_tenant
```
The script is idempotent — existing rows are skipped.

## AI agents

Four specialists routed by `agents.orchestrator.Orchestrator`. Routing is keyword-first (cheap), with a fallback Claude classification call for unmatched queries.

| Agent      | Tools (Anthropic tool-use schemas) |
|------------|------------------------------------|
| HR         | `list_employees`, `list_pending_leaves`, `approve_leave`, `reject_leave` |
| Payroll    | `calculate_payslip`, `list_payroll_runs`, `get_payslip_for_run`, `detect_anomalies_for_run` |
| Finance    | `salary_aggregate`, `department_spend`, `payroll_year_summary`, `sync_zoho` |
| Compliance | `list_upcoming`, `list_overdue`, `filings_for_period`, `mark_filed` |

`BaseAgent.run` loops on tool-use up to `max_iterations` (default 6), uses adaptive thinking, and applies `cache_control={"type": "ephemeral"}` on the system prompt for prompt caching. Per-tenant context (e.g. `{company_name}`) is rendered into the system prompt — that lowers cache hit rate but each tenant still gets a warm cache.

The orchestrator writes a row to `agent_logs` after every chat turn (best-effort, non-fatal).

## Scheduler jobs

Defined in `backend/services/scheduler.py`, all in IST (`Asia/Kolkata`). Skipped when `APP_ENV=test`.

| Cron                       | Job                                       | Function                       |
|----------------------------|-------------------------------------------|--------------------------------|
| 25th of month, 09:00 IST   | Payroll reminder ping per tenant          | `job_payroll_reminder_25th`    |
| 1st of month, 02:00 IST    | Auto-run payroll for previous month       | `job_auto_run_payroll_1st`     |
| 7th of month, 09:00 IST    | PF/ESI/TDS upcoming-deadline alert        | `job_compliance_alert_7th`     |
| Daily 09:00 IST            | HR pending-leaves count per tenant        | `job_hr_pending_leaves_daily`  |

## Useful commands

```bash
# Backend (Docker, recommended)
docker-compose up --build
docker-compose exec backend alembic upgrade head
docker-compose exec backend python -m backend.scripts.seed_first_tenant
docker-compose exec backend pytest tests/ -v

# Backend (local Python — run from repo root so `backend.main` resolves)
docker-compose up -d postgres redis
PYTHONPATH=. uvicorn backend.main:app --reload

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
cd frontend && npm run lint
cd frontend && npm run build

# Whole stack via nginx (port 80)
docker-compose up --build
# Frontend at http://localhost — backend at http://localhost/api/v1/...
```

## Deployment

- **Local**: `docker-compose up --build` (postgres + redis + backend + frontend + nginx).
- **Render** (free tier viable for demo): connect the repo to Render → pick "Blueprint" → it reads `render.yaml` and provisions everything. Set `SEED_ADMIN_PASSWORD`, `ANTHROPIC_API_KEY`, `CORS_ORIGINS`, and `VITE_API_URL` in the Render dashboard. Full walkthrough in `DEPLOY.md`.
- **Self-hosted**: build the Docker images, push to your registry, point `*.payroll.anutech.in` DNS at the LB, terminate TLS at the LB or extend `nginx.conf`.

## What not to do

- **Don't bypass `TenantMiddleware` / `get_tenant_session`.** There are zero legitimate reasons to query tenant data without them.
- **Don't store secrets in code.** Use env vars; `.env` is in `.gitignore`.
- **Don't add ORM model fields without updating `migrations/tenant_schema.sql`.** Onboarding runs raw SQL, not Alembic — keep them in sync.
- **Don't mock the payroll calculator in tests.** Test the real engine.
- **Don't roll your own JWT or password hashing.** Use the helpers in `core/security.py`.
- **Don't commit `frontend/dist/`, `node_modules/`, `__pycache__/`, or `.env`.**
- **Don't change frozen contracts** (`BaseAgent`, `get_tenant_session`, master/tenant models) without coordination.

## Related docs

- `README.md` — product overview, quick start, smoke test
- `DEPLOY.md` — step-by-step Render deployment
- `ZOHO_SETUP.md` — one-time OAuth setup for Zoho Books integration
