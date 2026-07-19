-- Sample data for local development / manual testing against the API gateway.
-- Not for production use. UUIDs are hardcoded so they're easy to reference
-- directly in requests (e.g. GET /envelopes/{id}) while poking at the API.
--
-- Run manually after `alembic upgrade head` has created the tables - see
-- docs/migrations.md. Not part of docker-entrypoint-initdb.d: those scripts
-- only run once, when the postgres volume is first created, at which point
-- the tables this script inserts into don't exist yet.

INSERT INTO auth.users (id, email, password_hash) VALUES
    ('00000000-0000-0000-0000-000000000001', 'dawid@example.com', 'placeholder-not-a-real-hash');

INSERT INTO budget.accounts (id, user_id, name, type, currency) VALUES
    ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000001', 'Checking account', 'checking', 'PLN'),
    ('00000000-0000-0000-0000-000000000102', '00000000-0000-0000-0000-000000000001', 'Savings account',  'savings',  'PLN');

INSERT INTO budget.payees (id, user_id, name) VALUES
    ('00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000001', 'Biedronka'),
    ('00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000001', 'Netflix'),
    ('00000000-0000-0000-0000-000000000203', '00000000-0000-0000-0000-000000000001', 'Landlord');

INSERT INTO budget.category_groups (id, user_id, name, sort_order) VALUES
    ('00000000-0000-0000-0000-000000000301', '00000000-0000-0000-0000-000000000001', 'Living costs',     1),
    ('00000000-0000-0000-0000-000000000302', '00000000-0000-0000-0000-000000000001', 'Quality of life',  2);

INSERT INTO budget.envelopes (id, user_id, category_group_id, name, target_amount) VALUES
    ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000301', 'Groceries',     800.00),
    ('00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000301', 'Rent',         1500.00),
    ('00000000-0000-0000-0000-000000000403', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000302', 'Subscriptions',  60.00);

INSERT INTO budget.envelope_allocations (id, envelope_id, month, assigned_amount) VALUES
    ('00000000-0000-0000-0000-000000000701', '00000000-0000-0000-0000-000000000401', '2026-07-01', 800.00),
    ('00000000-0000-0000-0000-000000000702', '00000000-0000-0000-0000-000000000402', '2026-07-01', 1500.00),
    ('00000000-0000-0000-0000-000000000703', '00000000-0000-0000-0000-000000000403', '2026-07-01',  60.00);

INSERT INTO transactions.statements (id, user_id, account_id, filename, format) VALUES
    ('00000000-0000-0000-0000-000000000501', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 'checking_july_2026.csv', 'csv');

INSERT INTO transactions.transactions (
    id, user_id, account_id, envelope_id, payee_id, statement_id,
    amount, currency, description, transaction_date, cleared, categorization_source
) VALUES
    ('00000000-0000-0000-0000-000000000601', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     '00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000501',
     -123.45, 'PLN', 'Groceries run', '2026-07-02', true, 'rule'),

    ('00000000-0000-0000-0000-000000000602', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     '00000000-0000-0000-0000-000000000403', '00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000501',
     -55.00, 'PLN', 'Monthly subscription', '2026-07-03', true, 'ml'),

    ('00000000-0000-0000-0000-000000000603', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     '00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000203', '00000000-0000-0000-0000-000000000501',
     -1500.00, 'PLN', 'July rent', '2026-07-05', true, 'rule'),

    ('00000000-0000-0000-0000-000000000604', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     NULL, NULL, '00000000-0000-0000-0000-000000000501',
     -19.99, 'PLN', 'Unrecognized card payment', '2026-07-10', false, NULL),

    ('00000000-0000-0000-0000-000000000605', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     '00000000-0000-0000-0000-000000000401', NULL, NULL,
     -30.00, 'PLN', 'Manual entry - corner shop', '2026-07-12', false, 'manual');
