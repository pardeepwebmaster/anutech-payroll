# Anutech Payroll — Engineering Guide

> **This file is read by every Claude session (lead and teammates) before any work. Treat it as the source of truth for architecture, conventions, and ownership.**

## Product

**Anutech Payroll** — multi-tenant SaaS payroll for Indian companies.
- Made by: Anutech (IT company, India)
- Domain: `payroll.anutech.in` (subdomain-per-tenant: `{tenant}.payroll.anutech.in`)

## Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Alembic, Pydantic v2
- **DB**: PostgreSQL 15 (schema-per-tenant isolation)
- **Cache/Queue**: Redis 7
- **Background jobs**: APScheduler (in-process)
- **AI**: Anthropic Claude API (`anthropic` SDK)
- **Frontend**: React 18 + Vite + TailwindCSS + react-router-dom + axios
- **Infra**: Docker Compose, nginx reverse proxy

## Multi-tenancy: schema-per-tenant

This is the **central architectural rule**. Get it wrong and tenants leak data.

1. **Master DB schema** (`public`) holds `tenants`, `subscription_plans`, `billing`. No tenant data here.
2. **Each tenant gets its own PostgreSQL schema** named after their slug (e.g. `anutech`).
3. **Every authenticated request** passes through `tenant_middleware`, which:
   - Decodes the JWT to get `tenant_schema`
   - Calls `SET search_path TO {tenant_schema}, public` on the request-scoped DB session
4. **Every ORM query** must use the request-scoped session — never construct a session that bypasses the middleware.
5. **Tenant onboarding** = create schema + run `tenant_schema.sql` DDL + seed initial data (one transaction).
6. **Subdomain routing**: nginx maps `{tenant}.payroll.anutech.in` → backend with `X-Tenant-Slug` header (used at login; JWT carries it after).

**Non-negotiable test**: a tenant's JWT must NEVER be able to read another tenant's rows. The integration test at `tests/test_tenant_isolation.py` enforces this and is required to pass before any merge.

## Project layout

```
anutech-payroll/
├── backend/
│   ├── main.py                       # FastAPI entry, router wiring, scheduler startup
│   ├── core/
│   │   ├── config.py                 # Pydantic Settings (env vars)
│   │   ├── database.py               # Engine + session factory + tenant schema router
│   │   ├── tenant_middleware.py      # JWT → tenant_schema → SET search_path
│   │   └── security.py               # JWT, password hashing, current_user dep
│   ├── models/
│   │   ├── master_models.py          # Tenant, SubscriptionPlan, Billing
│   │   └── tenant_models.py          # Employee, PayrollRun, Payslip, Leave, ComplianceFiling, AgentLog
│   ├── routers/                      # OWNED BY: backend-api
│   │   ├── auth.py                   # register, login, password reset, JWT issue
│   │   ├── employees.py              # CRUD with tenant scope
│   │   ├── payroll.py                # run-payroll, payslips, PDF download
│   │   ├── leaves.py                 # apply, approve, balance
│   │   ├── compliance.py             # PF/ESI/TDS filing tracker
│   │   ├── reports.py                # salary + compliance reports
│   │   └── ai_chat.py                # proxy to agents.orchestrator
│   ├── services/                     # OWNED BY: payroll-engine
│   │   ├── payroll_calculator.py     # Indian payroll engine (canonical rules — see below)
│   │   ├── zoho_books.py             # per-tenant Zoho Books OAuth + sync
│   │   ├── email_service.py          # WeasyPrint payslip PDF + SMTP
│   │   └── scheduler.py              # APScheduler jobs
│   ├── agents/                       # OWNED BY: ai-agents
│   │   ├── __init__.py               # BaseAgent ABC (frozen contract)
│   │   ├── orchestrator.py           # routes queries to specialist agents
│   │   ├── hr_agent.py               # HR (employees, leaves)
│   │   ├── payroll_agent.py          # payroll calculation, anomaly detection
│   │   ├── finance_agent.py          # Zoho Books, expense reports
│   │   └── compliance_agent.py       # PF/ESI/TDS deadlines
│   ├── migrations/
│   │   ├── master_schema.sql         # DDL for master DB
│   │   └── tenant_schema.sql         # DDL template for new tenant
│   ├── alembic.ini
│   ├── alembic/                      # versioned migrations
│   └── requirements.txt
├── frontend/                         # OWNED BY: frontend
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── lib/                      # api client, auth helpers, theme
│       ├── admin/                    # Dashboard, Employees, RunPayroll, Reports, Compliance, AIChat
│       └── employee/                 # MyPayslips, LeaveApply, MyProfile
├── tests/
│   ├── conftest.py                   # fixtures: test DB, tenant context, auth client
│   ├── test_payroll_calculator.py    # OWNED BY: payroll-engine
│   ├── test_tenant_isolation.py      # OWNED BY: backend-api (enforces multi-tenancy)
│   └── test_*.py
├── docker-compose.yml                # OWNED BY: devops-docs
├── nginx.conf                        # OWNED BY: devops-docs
├── .env.example                      # OWNED BY: devops-docs
└── README.md                         # OWNED BY: devops-docs
```

## File ownership rules (Phase 1 team)

| Teammate         | Writes                                                                | Reads everything else |
|------------------|-----------------------------------------------------------------------|----------------------|
| `backend-api`    | `backend/routers/**`, `tests/test_tenant_isolation.py`                | yes |
| `payroll-engine` | `backend/services/**`, `tests/test_payroll_calculator.py`, `tests/test_services_*.py` | yes |
| `ai-agents`      | `backend/agents/**`, `tests/test_agents_*.py`                         | yes |
| `frontend`       | `frontend/src/**`, `frontend/public/**`                               | API contracts only |
| `devops-docs`    | `docker-compose.yml`, `nginx.conf`, `.env.example`, `README.md`, `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore`, `.github/workflows/**` | yes |

**Cross-tree edits go through the lead.** If you need a change in someone else's tree, send `SendMessage` to the lead with the request.

**Frozen contracts** (don't mutate without lead approval):
- `backend/agents/__init__.py:BaseAgent` — both `ai-agents` and `backend-api` code to it
- `backend/core/database.py:get_tenant_session` — every router uses this dependency
- `backend/models/*.py` — schema changes require an Alembic migration + lead review

## Indian payroll calculation (canonical)

`backend/services/payroll_calculator.py` is the single source of truth. Anyone displaying a payslip must call this — never re-implement.

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

# Professional Tax (Maharashtra default)
pt            = 200

# Tax Deducted at Source — annual slab, deducted monthly
tds           = compute_tds_monthly(annual_gross)   # see slab table in module

net_pay       = gross - pf_employee - esi_employee - pt - tds
```

**Rounding**: all amounts stored as `Numeric(12, 2)`. Round half-up to 2 decimals for storage and display.

## Conventions

### Python
- Use type hints everywhere (`from __future__ import annotations`).
- Pydantic v2 for request/response schemas; SQLAlchemy 2.x style (`Mapped`, `mapped_column`).
- Async FastAPI handlers; sync DB calls are fine (psycopg2 is sync — use `Depends(get_tenant_session)`).
- Errors: raise `HTTPException` with explicit status codes. Don't return error dicts.
- Logging: `import logging; log = logging.getLogger(__name__)` — no `print`.
- One file = one responsibility. Don't merge routers.

### Naming
- Routes: `/api/v1/<resource>` (kebab when multi-word: `/api/v1/payroll-runs`)
- DB tables: snake_case plural (`employees`, `payroll_runs`)
- Pydantic schemas: `EmployeeCreate`, `EmployeeRead`, `EmployeeUpdate`
- Tests: `test_<module>_<behavior>`

### Frontend
- React 18 with hooks; **no class components**.
- File names: `PascalCase.jsx` for components, `camelCase.js` for utilities.
- Styling: Tailwind utility classes; theme color is **`#7F77DD`** (Anutech purple) — defined as `primary` in `tailwind.config.js`.
- API calls go through `src/lib/api.js` (axios instance with JWT interceptor).
- Tables: search + filter + CSV/PDF export are built into a shared `<DataTable>` component.

### Git
- One commit per logical change. Conventional Commits style (`feat:`, `fix:`, `chore:`, `docs:`).
- Never commit `.env`, `*.db`, `node_modules`, `__pycache__`.
- Run tests before committing.

## Environment variables

All defined in `.env.example`. Required for backend to start:
- `DATABASE_URL` — postgres://user:pass@host:5432/anutech_payroll
- `MASTER_SCHEMA` — usually `public`
- `JWT_SECRET` — long random string
- `JWT_ALGORITHM` — `HS256`
- `JWT_EXPIRES_MINUTES` — `1440`
- `ANTHROPIC_API_KEY` — for AI agents
- `ANTHROPIC_MODEL` — model id (verify current latest with lead before coding agents)
- `REDIS_URL` — redis://redis:6379/0
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
- `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN` (per-tenant in DB, but fallback global allowed for testing)
- `APP_ENV` — `dev` | `prod`
- `LOG_LEVEL` — `INFO` | `DEBUG`

## Subscription plans (seed)

| Plan | Price/month | Max employees | Features |
|------|-------------|----------------|----------|
| Starter | ₹1,999 | 10 | basic |
| Growth  | ₹4,999 | 25 | + AI agents |
| Scale   | ₹8,999 | 50 | + all agents + priority |

## First tenant seed (for verification)

- **Slug**: `anutech` → schema `anutech` → `anutech.payroll.anutech.in`
- **Plan**: Scale
- **Employees** (₹ monthly gross):

| Name | Role | Department | Gross |
|------|------|------------|-------|
| Pardeep Sharma | Director + Sales Head | Leadership | 1,80,000 |
| Abhishek | CTO | Engineering | 35,000 |
| Hitesh Baghel | COO + HR | Operations | 52,000 |
| Pawan | Developer | Engineering | 24,000 |
| Ananya Sharma | Sales Executive | Sales | 90,000 |
| Darshan Kumar | Marketing Executive | Sales | 20,000 |
| Ranjeet Raj | Support | Operations | 38,000 |
| Mayank Sharma | Accounts | Accounts | 80,000 |

## Scheduler jobs

| Cron | Job | Owner |
|------|-----|-------|
| 25th of month, 09:00 IST | Payroll Agent reminder ping | payroll-engine |
| 1st of month, 02:00 IST | Auto-run payroll + Zoho sync (configurable per tenant) | payroll-engine |
| 7th of month, 09:00 IST | PF/ESI/TDS deadline alert | compliance-agent |
| Daily 09:00 IST | HR Agent — pending leave approvals | hr-agent |

All times in IST. Tenant can opt out per job.

## What not to do

- **Don't bypass tenant_middleware**. There are zero legitimate reasons to query tenant data without it.
- **Don't store secrets in code**. Use env vars; `.env` is in `.gitignore`.
- **Don't add new ORM model fields without Alembic migrations**. The `tenant_schema.sql` template must stay in sync — there's a CI check for that.
- **Don't mock the payroll calculator in tests**. Test the real engine. Mocking it defeats the point.
- **Don't roll your own JWT or password hashing**. Use the helpers in `core/security.py`.
- **Don't add a teammate that owns files outside its tree** (Phase 1 team). Use the lead to broker.

## Useful commands

```bash
# Backend
docker-compose up -d postgres redis
cd backend && uvicorn main:app --reload
alembic upgrade head
pytest tests/ -v

# Frontend
cd frontend && npm install && npm run dev

# Full stack
docker-compose up --build

# Seed first tenant
docker-compose exec backend python -m scripts.seed_first_tenant
```
