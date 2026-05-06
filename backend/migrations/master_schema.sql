-- Master DB schema (lives in `public`).
-- Idempotent: safe to run on an empty DB or alongside Alembic.

CREATE TABLE IF NOT EXISTS public.subscription_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(64) UNIQUE NOT NULL,
    max_employees   INTEGER NOT NULL,
    price_monthly   NUMERIC(10, 2) NOT NULL,
    price_yearly    NUMERIC(10, 2) NOT NULL,
    features_json   VARCHAR(2048) NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(64) NOT NULL UNIQUE,
    schema_name     VARCHAR(64) NOT NULL UNIQUE,
    plan_id         UUID NOT NULL REFERENCES public.subscription_plans(id),
    status          VARCHAR(32) NOT NULL DEFAULT 'active',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_tenants_slug ON public.tenants(slug);

CREATE TABLE IF NOT EXISTS public.billing (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    amount          NUMERIC(10, 2) NOT NULL,
    period          VARCHAR(7) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    paid_at         TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_billing_tenant ON public.billing(tenant_id);

-- Seed plans (idempotent via ON CONFLICT)
INSERT INTO public.subscription_plans (name, max_employees, price_monthly, price_yearly)
VALUES
    ('Starter', 10, 1999, 19990),
    ('Growth',  25, 4999, 49990),
    ('Scale',   50, 8999, 89990)
ON CONFLICT (name) DO NOTHING;
