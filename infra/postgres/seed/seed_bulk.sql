-- Bulk sample data for load/UX testing: enough rows that tables scroll, groups
-- collapse and totals stop being trivially checkable by eye.
--
-- Separate from seed_data.sql, which stays small and hand-written with stable
-- UUIDs you can paste into requests. This one generates its rows, so it is only
-- useful in bulk - read seed_data.sql first if you want to understand the shape
-- of the data.
--
-- Run manually after `alembic upgrade head`, and after seed_data.sql (it reuses
-- that file's user). Re-runnable: every insert is ON CONFLICT DO NOTHING and all
-- ids are derived from the row index, so running it twice changes nothing.
--
-- Dates are anchored on the current month, not a fixed one, so "This month" is
-- always fully populated no matter when this is loaded.

BEGIN;

-- Row counts. Lower these if the frontend feels unusable rather than merely
-- busy - that difference is exactly what this file exists to find out.
\set n_payees 40
\set n_envelopes 36
\set n_transactions 1500
\set n_months 12

-- --------------------------------------------------------------------------
-- Accounts. seed_data.sql already has a checking and a savings account, but
-- every transaction in it belongs to the checking one, so filtering by account
-- looked broken - there was nothing else to filter to.
-- --------------------------------------------------------------------------
INSERT INTO budget.accounts (id, user_id, name, type, currency)
SELECT
    ('a0000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '00000000-0000-0000-0000-000000000001',
    name,
    type,
    'PLN'
FROM (VALUES
    (1, 'Credit card',    'credit_card'),
    (2, 'Cash wallet',    'cash'),
    (3, 'Joint account',  'checking')
) AS t(i, name, type)
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------------------------------------
-- Payees. Names are cycled from a fixed list so the Payees screen and the
-- transaction table read like real merchants rather than "Payee 27".
--
-- Deliberately disjoint from the names seed_data.sql inserts and from the ones
-- the statement-import tests feed in: `budget.payees` has no unique constraint
-- on `name`, and `get_or_create_payee` looks a payee up by name, so a duplicate
-- name is a landmine for anything importing a statement.
-- --------------------------------------------------------------------------
INSERT INTO budget.payees (id, user_id, name)
SELECT
    ('b0000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '00000000-0000-0000-0000-000000000001',
    names.name || CASE WHEN i > array_length(names.all_names, 1) THEN ' ' || i::text ELSE '' END
FROM generate_series(1, :n_payees) AS i
CROSS JOIN LATERAL (
    SELECT arr AS all_names, arr[1 + ((i - 1) % array_length(arr, 1))] AS name
    FROM (SELECT ARRAY[
        'Delikatesy Centrum', 'Lidl', 'Żabka', 'Auchan', 'Kaufland', 'Rossmann',
        'Orlen', 'Shell', 'BP', 'Uber', 'Bolt', 'Koleje Mazowieckie',
        'HBO Max', 'Spotify', 'Allegro', 'Empik', 'Media Markt', 'IKEA',
        'Apteka Gemini', 'Decathlon', 'Zalando', 'Booking.com', 'Ryanair',
        'Pyszne.pl', 'Green Caffè', 'Costa Coffee', 'Multikino', 'Pracownia Kawy',
        'Enea', 'PGNiG', 'Orange', 'Play', 'UPC', 'Wodociągi',
        'Wspólnota mieszkaniowa', 'Salon fryzjerski', 'Serwis rowerowy', 'Księgarnia',
        'Kwiaciarnia', 'Piekarnia Wiejska'
    ] AS arr) AS a
) AS names
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------------------------------------
-- Category groups. Six of them, so the Envelopes ledger is long enough that
-- collapsing a group actually matters and drag & drop has somewhere to go.
-- --------------------------------------------------------------------------
INSERT INTO budget.category_groups (id, user_id, name, sort_order)
SELECT
    ('c0000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '00000000-0000-0000-0000-000000000001',
    name,
    i + 2
FROM (VALUES
    (1, 'Transport'),
    (2, 'Zdrowie'),
    (3, 'Dom i rachunki'),
    (4, 'Rozrywka'),
    (5, 'Oszczędności'),
    (6, 'Nieregularne')
) AS t(i, name)
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------------------------------------
-- Envelopes, spread round-robin across the six new groups.
-- --------------------------------------------------------------------------
INSERT INTO budget.envelopes (id, user_id, category_group_id, name, target_amount)
SELECT
    ('d0000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '00000000-0000-0000-0000-000000000001',
    ('c0000000-0000-0000-0000-' || lpad((1 + ((i - 1) % 6))::text, 12, '0'))::uuid,
    names.arr[1 + ((i - 1) % array_length(names.arr, 1))]
        || CASE WHEN i > array_length(names.arr, 1) THEN ' ' || i::text ELSE '' END,
    -- Targets from 50 to 1400, varied but deterministic.
    (50 + ((i * 137) % 1350))::numeric
FROM generate_series(1, :n_envelopes) AS i
CROSS JOIN LATERAL (
    SELECT ARRAY[
        'Paliwo', 'Bilety', 'Taksówki', 'Serwis auta', 'Parkingi',
        'Leki', 'Wizyty lekarskie', 'Siłownia', 'Suplementy',
        'Prąd', 'Gaz', 'Woda', 'Internet', 'Telefon', 'Czynsz dodatkowy',
        'Kino', 'Koncerty', 'Gry', 'Książki', 'Kawiarnie',
        'Poduszka bezpieczeństwa', 'Wakacje', 'Nowy laptop', 'Remont',
        'Prezenty', 'Ubrania', 'Fryzjer', 'Kosmetyki', 'Zwierzęta',
        'Szkolenia', 'Subskrypcje IT', 'Hobby', 'Ogród', 'Darowizny',
        'Naprawy', 'Bufor'
    ] AS arr
) AS names
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------------------------------------
-- Monthly allocations for every generated envelope, for the last n_months
-- months including this one. Assigned amounts drift month to month so the
-- envelope-detail history chart has something to draw.
-- --------------------------------------------------------------------------
INSERT INTO budget.envelope_allocations (id, envelope_id, month, assigned_amount, target_amount)
SELECT
    ('e0000000-0000-0000-0000-' || lpad((i * 100 + m)::text, 12, '0'))::uuid,
    ('d0000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    (date_trunc('month', CURRENT_DATE) - (m || ' months')::interval)::date,
    (50 + ((i * 137) % 1350) + (((i + m) * 53) % 200) - 100)::numeric,
    (50 + ((i * 137) % 1350))::numeric
FROM generate_series(1, :n_envelopes) AS i
CROSS JOIN generate_series(0, :n_months - 1) AS m
ON CONFLICT (envelope_id, month) DO NOTHING;

-- --------------------------------------------------------------------------
-- One statement per account, so imported rows have something to belong to.
-- --------------------------------------------------------------------------
INSERT INTO transactions.statements (id, user_id, account_id, filename, format)
SELECT
    ('f0000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '00000000-0000-0000-0000-000000000001',
    ('a0000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    'bulk_import_' || i::text || '.csv',
    'csv'
FROM generate_series(1, 3) AS i
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------------------------------------
-- The bulk of it. Deterministic pseudo-random spread (multiply by a prime,
-- take a modulus) rather than random(), so two runs produce identical data and
-- a screenshot can be compared against a later one.
--
-- Every 23rd row is income and positive; every 17th is left uncategorised, to
-- exercise the "Uncategorized" fallback and the alerts that come with it.
-- --------------------------------------------------------------------------
INSERT INTO transactions.transactions (
    id, user_id, account_id, envelope_id, payee_id, statement_id,
    amount, currency, description, transaction_date, cleared, categorization_source
)
SELECT
    ('99000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '00000000-0000-0000-0000-000000000001',
    CASE (i % 4)
        WHEN 0 THEN '00000000-0000-0000-0000-000000000101'::uuid
        ELSE ('a0000000-0000-0000-0000-' || lpad((1 + (i % 3))::text, 12, '0'))::uuid
    END,
    CASE WHEN i % 17 = 0 THEN NULL
         ELSE ('d0000000-0000-0000-0000-' || lpad((1 + ((i * 7) % :n_envelopes))::text, 12, '0'))::uuid
    END,
    CASE WHEN i % 19 = 0 THEN NULL
         ELSE ('b0000000-0000-0000-0000-' || lpad((1 + ((i * 11) % :n_payees))::text, 12, '0'))::uuid
    END,
    CASE WHEN i % 5 = 0 THEN NULL
         ELSE ('f0000000-0000-0000-0000-' || lpad((1 + (i % 3))::text, 12, '0'))::uuid
    END,
    CASE WHEN i % 23 = 0
         THEN (2000 + ((i * 31) % 4000))::numeric
         ELSE -((5 + ((i * 173) % 40000))::numeric / 100)
    END,
    'PLN',
    CASE WHEN i % 23 = 0 THEN 'Wynagrodzenie' ELSE 'Płatność kartą #' || i::text END,
    -- Spread evenly backwards from the END of the current month, not from
    -- today. Anchoring on CURRENT_DATE gave the current month only as many rows
    -- as days elapsed - load it on the 2nd and the default "This month" view
    -- shows a dozen transactions while every other month has ~130. The cost is
    -- that part of the current month is dated in the future; for test data that
    -- is a fair trade for a screen that is actually populated on arrival.
    ((date_trunc('month', CURRENT_DATE) + interval '1 month - 1 day')::date
        - ((i * 7) % (:n_months * 30))),
    i % 11 <> 0,
    (ARRAY['rule', 'ml', 'manual'])[1 + (i % 3)]
FROM generate_series(1, :n_transactions) AS i
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- What landed:
--   SELECT count(*) FROM transactions.transactions;
--   SELECT count(*) FROM budget.envelopes;
--   SELECT date_trunc('month', transaction_date) AS m, count(*)
--     FROM transactions.transactions GROUP BY 1 ORDER BY 1;
