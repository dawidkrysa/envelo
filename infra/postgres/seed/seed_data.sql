-- Sample data for local development / manual testing against the API gateway.
-- Not for production use. UUIDs are hardcoded so they're easy to reference
-- directly in requests (e.g. GET /envelopes/{id}) while poking at the API.
--
-- Run manually after `alembic upgrade head` has created the tables - see
-- docs/migrations.md. Not part of docker-entrypoint-initdb.d: those scripts
-- only run once, when the postgres volume is first created, at which point
-- the tables this script inserts into don't exist yet.

-- Sign in as dawid@example.com / envelo-dev-password. A DEVELOPMENT-ONLY
-- credential, published here on purpose: never seed it into a database anyone
-- else can reach. DO UPDATE rather than DO NOTHING so that re-running this
-- script also fixes a database seeded before the password was real (when the
-- hash was a placeholder nothing could log in with).
INSERT INTO auth.users (id, email, password_hash) VALUES
    ('00000000-0000-0000-0000-000000000001', 'dawid@example.com',
     '$argon2id$v=19$m=65536,t=3,p=4$PkmSm6r2rwlfSh8gCxskNw$MpksT4r2f3gsjFXpE0iVrxNhlO65z6CES5OBYDsC98M')
ON CONFLICT (id) DO UPDATE SET password_hash = EXCLUDED.password_hash;

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

-- Second batch: "this month"'s data, dated relative to CURRENT_DATE instead
-- of hardcoded like the July batch above. `range_to_dates("this")`
-- (frontend/src/utils.py) filters everything on the Envelopes/Dashboard/
-- Transactions screens to the real current calendar month, so a
-- hardcoded-month seed goes stale (shows nothing) the moment the wall clock
-- crosses into a new month. This batch stays "current" no matter when the
-- script is (re-)run; the July batch is kept as-is for testing the
-- "last3"/"year" transaction ranges.
--
-- ON CONFLICT DO NOTHING throughout: this script is meant to be re-run
-- every time the current month rolls over, and a dev DB may already have
-- real allocations/transactions for the current month from manual UI
-- testing by the time it's run - this batch only fills gaps, it never
-- clobbers rows that are already there.
INSERT INTO budget.payees (id, user_id, name) VALUES
    ('00000000-0000-0000-0000-000000000204', '00000000-0000-0000-0000-000000000001', 'Employer')
ON CONFLICT (id) DO NOTHING;

INSERT INTO budget.envelope_allocations (id, envelope_id, month, assigned_amount) VALUES
    ('00000000-0000-0000-0000-000000000704', '00000000-0000-0000-0000-000000000401', date_trunc('month', CURRENT_DATE)::date, 800.00),
    ('00000000-0000-0000-0000-000000000705', '00000000-0000-0000-0000-000000000402', date_trunc('month', CURRENT_DATE)::date, 1500.00),
    ('00000000-0000-0000-0000-000000000706', '00000000-0000-0000-0000-000000000403', date_trunc('month', CURRENT_DATE)::date, 60.00)
ON CONFLICT (envelope_id, month) DO NOTHING;

INSERT INTO transactions.statements (id, user_id, account_id, filename, format) VALUES
    ('00000000-0000-0000-0000-000000000502', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 'checking_this_month.csv', 'csv')
ON CONFLICT (id) DO NOTHING;

INSERT INTO transactions.transactions (
    id, user_id, account_id, envelope_id, payee_id, statement_id,
    amount, currency, description, transaction_date, cleared, categorization_source
) VALUES
    -- Income - no envelope_id, same as an unrecognized/unclassified
    -- transaction would have: it funds "left to assign" without belonging
    -- to any one envelope's spent total.
    ('00000000-0000-0000-0000-000000000606', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     NULL, '00000000-0000-0000-0000-000000000204', '00000000-0000-0000-0000-000000000502',
     4500.00, 'PLN', 'Salary', date_trunc('month', CURRENT_DATE)::date, true, 'manual'),

    ('00000000-0000-0000-0000-000000000607', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     '00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000502',
     -110.20, 'PLN', 'Groceries run', (date_trunc('month', CURRENT_DATE) + interval '1 day')::date, true, 'rule'),

    ('00000000-0000-0000-0000-000000000608', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     '00000000-0000-0000-0000-000000000403', '00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000502',
     -55.00, 'PLN', 'Monthly subscription', (date_trunc('month', CURRENT_DATE) + interval '2 days')::date, true, 'ml'),

    ('00000000-0000-0000-0000-000000000609', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     '00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000203', '00000000-0000-0000-0000-000000000502',
     -1500.00, 'PLN', 'Rent', (date_trunc('month', CURRENT_DATE) + interval '4 days')::date, true, 'rule'),

    ('00000000-0000-0000-0000-000000000610', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101',
     '00000000-0000-0000-0000-000000000401', NULL, NULL,
     -22.50, 'PLN', 'Manual entry - corner shop', (date_trunc('month', CURRENT_DATE) + interval '6 days')::date, false, 'manual')
ON CONFLICT (id) DO NOTHING;
