-- Per-tenant DDL template.
-- Executed inside a freshly created schema during tenant onboarding.
-- The runner sets search_path to the tenant schema before running this.

-- gen_random_uuid() is provided by pgcrypto. Master schema creates the
-- extension; the tenant schema inherits it via search_path.

CREATE TABLE IF NOT EXISTS employees (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE,
    role            VARCHAR(128) NOT NULL,
    department      VARCHAR(128) NOT NULL,
    basic_salary    NUMERIC(12, 2) NOT NULL,
    joining_date    DATE NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'active',
    pan             VARCHAR(10),
    bank_account    VARCHAR(64),
    bank_ifsc       VARCHAR(16),
    password_hash   VARCHAR(255),
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_employees_status ON employees(status);

CREATE TABLE IF NOT EXISTS payroll_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',
    total_gross     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    total_net       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    run_by          UUID,
    run_at          TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (year, month)
);

CREATE TABLE IF NOT EXISTS payslips (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id),
    payroll_run_id      UUID NOT NULL REFERENCES payroll_runs(id),
    gross               NUMERIC(12, 2) NOT NULL,
    basic               NUMERIC(12, 2) NOT NULL,
    hra                 NUMERIC(12, 2) NOT NULL,
    special_allowance   NUMERIC(12, 2) NOT NULL,
    pf_employee         NUMERIC(12, 2) NOT NULL,
    pf_employer         NUMERIC(12, 2) NOT NULL,
    esi_employee        NUMERIC(12, 2) NOT NULL,
    esi_employer        NUMERIC(12, 2) NOT NULL,
    pt                  NUMERIC(12, 2) NOT NULL,
    tds                 NUMERIC(12, 2) NOT NULL,
    net_pay             NUMERIC(12, 2) NOT NULL,
    pdf_url             VARCHAR(512),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, payroll_run_id)
);

CREATE INDEX IF NOT EXISTS ix_payslips_run ON payslips(payroll_run_id);
CREATE INDEX IF NOT EXISTS ix_payslips_employee ON payslips(employee_id);

CREATE TABLE IF NOT EXISTS leaves (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID NOT NULL REFERENCES employees(id),
    type            VARCHAR(32) NOT NULL,
    from_date       DATE NOT NULL,
    to_date         DATE NOT NULL,
    reason          TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    approved_by     UUID REFERENCES employees(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_leaves_employee ON leaves(employee_id);
CREATE INDEX IF NOT EXISTS ix_leaves_status ON leaves(status);

CREATE TABLE IF NOT EXISTS compliance_filings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            VARCHAR(32) NOT NULL,
    period          VARCHAR(7) NOT NULL,
    due_date        DATE NOT NULL,
    filed_date      DATE,
    status          VARCHAR(32) NOT NULL DEFAULT 'due',
    amount          NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name      VARCHAR(64) NOT NULL,
    action          VARCHAR(255) NOT NULL,
    input_summary   TEXT,
    result          TEXT,
    tenant_id       UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_agent_logs_agent ON agent_logs(agent_name);
