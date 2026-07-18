-- Tables for the schemas created in 01_create_schemas.sql.
-- Mirrors docs/erd.md. `notifications` and `analytics` are planned schemas
-- with no tables yet (see docs/erd.md § Envelo's own additions).

CREATE TABLE auth.users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE budget.accounts (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES auth.users (id),
    name       text NOT NULL,
    type       text NOT NULL CHECK (type IN ('checking', 'savings', 'credit_card', 'cash')),
    currency   text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON budget.accounts (user_id);

CREATE TABLE budget.payees (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users (id),
    name    text NOT NULL
);

CREATE INDEX ON budget.payees (user_id);

CREATE TABLE budget.category_groups (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES auth.users (id),
    name       text NOT NULL,
    sort_order int NOT NULL
);

CREATE INDEX ON budget.category_groups (user_id);

CREATE TABLE budget.envelopes (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid NOT NULL REFERENCES auth.users (id),
    category_group_id  uuid NOT NULL REFERENCES budget.category_groups (id),
    name               text NOT NULL,
    target_amount      numeric,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON budget.envelopes (user_id);
CREATE INDEX ON budget.envelopes (category_group_id);

CREATE TABLE budget.envelope_allocations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    envelope_id     uuid NOT NULL REFERENCES budget.envelopes (id),
    month           date NOT NULL,
    assigned_amount numeric NOT NULL,
    UNIQUE (envelope_id, month)
);

CREATE TABLE transactions.statements (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES auth.users (id),
    account_id  uuid NOT NULL REFERENCES budget.accounts (id),
    filename    text NOT NULL,
    format      text NOT NULL CHECK (format IN ('csv', 'mt940', 'ofx')),
    imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON transactions.statements (user_id);
CREATE INDEX ON transactions.statements (account_id);

CREATE TABLE transactions.transactions (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              uuid NOT NULL REFERENCES auth.users (id),
    account_id           uuid NOT NULL REFERENCES budget.accounts (id),
    envelope_id          uuid REFERENCES budget.envelopes (id),
    payee_id             uuid REFERENCES budget.payees (id),
    statement_id         uuid REFERENCES transactions.statements (id),
    amount               numeric NOT NULL,
    currency             text NOT NULL,
    description          text,
    transaction_date     date NOT NULL,
    cleared              boolean NOT NULL DEFAULT false,
    categorization_source text CHECK (categorization_source IN ('rule', 'ml', 'manual'))
);

CREATE INDEX ON transactions.transactions (user_id);
CREATE INDEX ON transactions.transactions (account_id);
CREATE INDEX ON transactions.transactions (envelope_id);
CREATE INDEX ON transactions.transactions (payee_id);
CREATE INDEX ON transactions.transactions (statement_id);
