# Anutech Payroll

Multi-tenant SaaS payroll management system for Indian companies. Built with Python 3.11 (FastAPI), PostgreSQL (schema-per-tenant), Redis, React 18, and Claude AI agents.

> **Made by:** Anutech (IT company, India)
> **Domain:** [payroll.anutech.in](https://payroll.anutech.in) — `{tenant}.payroll.anutech.in` per tenant

## Features

- **Multi-tenant** — schema-per-tenant Postgres isolation, enforced at the DB level
- **Indian payroll engine** — PF, ESI, TDS (new regime slabs), Professional Tax
- **Employee CRUD + CSV export**
- **Payroll runs** — one-click monthly run, payslip PDF generation (WeasyPrint), email delivery
- **Leave management** — apply, approve, balance tracking
- **Compliance tracker** — PF / ESI / TDS / PT due-date dashboard
- **Reports** — annual salary, department spend, payroll summary
- **AI assistant** (Claude Opus 4.7) — orchestrator routes queries to HR / payroll / finance / compliance specialists
- **Scheduler** — APScheduler IST cron jobs (25th payroll reminder, 1st auto-run, 7th compliance alert, daily HR check)
- **Zoho Books sync** — per-tenant OAuth, expense entries from payroll runs
- **Subscription plans** — Starter ₹1,999 · Growth ₹4,999 · Scale ₹8,999 / month

## Stack

| Layer    | Tech |
|----------|------|
| Backend  | Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 |
| DB       | PostgreSQL 15 (schema-per-tenant) |
| Cache    | Redis 7 |
| AI       | Anthropic Claude API (`claude-opus-4-7`) |
| Frontend | React 18 · Vite · TailwindCSS · react-router-dom · axios |
| Infra    | Docker Compose · nginx |

## Quick start (local dev with Docker)

### 1. Configure environment

```bash
cp .env.example .env
```

Fill in `JWT_SECRET` (any long random string), `ANTHROPIC_API_KEY`, and SMTP / Zoho credentials if you need those flows. The rest have working defaults for local Docker.

### 2. Bring up the stack

```bash
docker-compose up --build
```

This starts:
- `postgres` (port 5432)
- `redis` (port 6379)
- `backend` FastAPI (port 8000) — `http://localhost:8000/docs`
- `frontend` React (port 3000) — `http://localhost:3000`
- `nginx` reverse proxy (port 80) — `http://localhost`

### 3. Run migrations and seed the first tenant

```bash
docker-compose exec backend alembic upgrade head
docker-compose exec backend python -m backend.scripts.seed_first_tenant
```

The seed creates the **Anutech** tenant on the **Scale** plan with 8 employees and one admin user. Override the admin password with `SEED_ADMIN_PASSWORD=...` before running.

### 4. Login

Visit `http://localhost:3000`. Sign in:
- **Tenant slug:** `anutech`
- **Email:** `pardeep@anutech.in`
- **Password:** `ChangeMe123!` (or whatever you set via `SEED_ADMIN_PASSWORD`)

## End-to-end smoke test

1. Login as admin → **Dashboard** shows 8 active employees, 0 pending leaves.
2. **Payroll → Run payroll** for the previous month → 8 payslips generated.
3. Click any payslip's **PDF** link → downloads payslip.pdf.
4. **AI Chat** → ask *"What's the next PF deadline?"* → Compliance agent answers.
5. **AI Chat** → ask *"Detect anomalies in the last payroll run"* → Payroll agent runs the calculator.
6. **Reports → Salary by month** → see the run.
7. Run tests:
   ```bash
   docker-compose exec backend pytest tests/ -v
   ```
   The `test_tenant_isolation.py` test enforces multi-tenant DB isolation; it must pass.

## Project layout

```
anutech-payroll/
├── backend/
│   ├── main.py
│   ├── core/         # config, db (tenant schema router), JWT, tenant middleware
│   ├── models/       # master + tenant SQLAlchemy
│   ├── routers/      # auth, employees, payroll, leaves, compliance, reports, ai_chat
│   ├── services/     # payroll_calculator (canonical engine), email, zoho, scheduler
│   ├── agents/       # BaseAgent + orchestrator + 4 specialists
│   ├── migrations/   # master_schema.sql + tenant_schema.sql
│   ├── alembic/
│   └── scripts/      # seed_first_tenant.py
├── frontend/
│   └── src/
│       ├── components/  # AdminLayout, EmployeeLayout, DataTable
│       ├── lib/         # api.js, auth.jsx, format.js
│       ├── pages/
│       │   ├── admin/   # Dashboard, Employees, RunPayroll, Reports, Compliance, Leaves, AIChat
│       │   └── employee/  # MyPayslips, LeaveApply, MyProfile
│       └── App.jsx
├── docker-compose.yml
├── nginx.conf
├── .env.example
├── CLAUDE.md         # engineering guide
└── tests/            # pytest, conftest with throwaway tenant fixture
```

## Multi-tenancy invariant

- Master DB (`public` schema) holds `tenants`, `subscription_plans`, `billing` only.
- Each tenant has a private PostgreSQL schema named after their slug.
- Every request: `tenant_middleware` decodes the JWT → `tenant_schema` field → DB session pins `SET search_path` to that schema for the request.
- Tenant onboarding creates the schema and runs `migrations/tenant_schema.sql`.
- The non-negotiable test `tests/test_tenant_isolation.py` proves cross-tenant queries cannot leak rows. Don't merge if it fails.

## Indian payroll calculation

Defined in `backend/services/payroll_calculator.py`. Anyone displaying payslip components calls this — never re-implement.

```
Basic              = gross * 40%
HRA                = basic * 40%
Special Allowance  = gross - basic - hra
PF Employee        = basic * 12%   (if basic > 0)
PF Employer        = basic * 12%
ESI Employee       = gross * 0.75% (only if gross <= 21,000)
ESI Employer       = gross * 3.25% (only if gross <= 21,000)
Professional Tax   = ₹200/month (Maharashtra default)
TDS                = annual income tax (new regime slabs) / 12
Net Pay            = gross - PF_Employee - ESI_Employee - PT - TDS
```

## API reference

`http://localhost:8000/docs` (Swagger UI, generated from FastAPI).

Key endpoints:
- `POST /api/v1/auth/register` — onboard a tenant (creates schema + admin)
- `POST /api/v1/auth/login` — JWT issue
- `GET /api/v1/employees` — list active employees
- `POST /api/v1/payroll/run` — run payroll for a month
- `GET /api/v1/payroll/payslips/{id}/pdf` — download payslip
- `POST /api/v1/leaves` — apply leave
- `POST /api/v1/ai-chat` — chat with the orchestrator

## Environment variables

See `.env.example` for the complete list. Required for backend boot:
- `DATABASE_URL`, `MASTER_SCHEMA`
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRES_MINUTES`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-opus-4-7`)
- `REDIS_URL`

Optional integrations (skipped if blank):
- `SMTP_*` for payslip email
- `ZOHO_*` for Books sync

## AI Agents

Four specialists routed by an orchestrator (deterministic keyword routing first, lightweight Claude classification fallback):

| Agent      | Tools |
|------------|-------|
| HR         | `list_employees`, `list_pending_leaves`, `approve_leave`, `reject_leave` |
| Payroll    | `calculate_payslip`, `list_payroll_runs`, `get_payslip_for_run`, `detect_anomalies_for_run` |
| Finance    | `salary_aggregate`, `department_spend`, `payroll_year_summary`, `sync_zoho` |
| Compliance | `list_upcoming`, `list_overdue`, `filings_for_period`, `mark_filed` |

Each agent uses adaptive thinking and prompt caching on its system prompt.

## Subdomain routing

Production: nginx maps `{tenant}.payroll.anutech.in` to the backend with an `X-Tenant-Slug` header. JWTs carry the tenant after login, so the header is mostly for the login + diagnostics path.

For local dev: browsers resolve `*.localhost` automatically, so `http://anutech.localhost` works once nginx is up.

## Production deployment

1. Build images: `docker-compose build`
2. Push to your registry (ECR, GHCR, etc.)
3. Set production env: `APP_ENV=prod`, real `JWT_SECRET`, production DB, real SMTP/Zoho/Anthropic keys.
4. Run migrations against the production master DB.
5. Seed plans (`master_schema.sql` does this with `ON CONFLICT DO NOTHING`).
6. Configure DNS: `*.payroll.anutech.in` A-record / CNAME pointing at the LB / nginx host.
7. TLS: terminate at a load balancer (Cloudflare / ALB) or extend `nginx.conf` with a Let's Encrypt sidecar.

## License

Proprietary — © Anutech.

## Engineering guide

See [`CLAUDE.md`](./CLAUDE.md) for architecture conventions, file ownership, and contribution rules.
