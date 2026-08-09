from decimal import Decimal

SEEDED_CATEGORY_GROUP_ID = "00000000-0000-0000-0000-000000000301"
SEEDED_ACCOUNT_ID = "00000000-0000-0000-0000-000000000101"


async def _create_envelope(client, name: str) -> str:
    response = await client.post(
        "/budget/envelopes",
        json={"category_group_id": SEEDED_CATEGORY_GROUP_ID, "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _assign(client, envelope_id: str, month: str, amount: str) -> None:
    response = await client.post(
        "/budget/envelope-allocations",
        json={"envelope_id": envelope_id, "month": month, "assigned_amount": amount},
    )
    assert response.status_code == 201


async def _spend(client, envelope_id: str | None, day: str, amount: str) -> None:
    payload = {
        "account_id": SEEDED_ACCOUNT_ID,
        "amount": amount,
        "currency": "PLN",
        "transaction_date": day,
    }
    if envelope_id is not None:
        payload["envelope_id"] = envelope_id
    response = await client.post("/budget/transactions", json=payload)
    assert response.status_code == 201


async def _forecast(client, **params) -> dict:
    response = await client.get("/budget/forecast", params=params)
    assert response.status_code == 200
    return response.json()


def _row(forecast: dict, envelope_id: str) -> dict:
    rows = [e for e in forecast["envelopes"] if e["envelope_id"] == envelope_id]
    assert rows, f"{envelope_id} missing from the forecast"
    return rows[0]


async def test_forecast_paces_month_to_date_spending_to_month_end(client):
    """Half the month gone with 100 spent projects 200 by the 31st."""
    envelope_id = await _create_envelope(client, "Paced")
    await _assign(client, envelope_id, "2026-03-01", "300.00")
    await _spend(client, envelope_id, "2026-03-10", "-100.00")

    # 15 of March's 31 days elapsed, so month-to-date covers 15/31 of the month.
    forecast = await _forecast(client, month="2026-03-01", asOf="2026-03-15")
    row = _row(forecast, envelope_id)

    assert Decimal(row["spent"]) == Decimal("100.00")
    assert Decimal(forecast["elapsed_fraction"]) == (
        Decimal("15") / Decimal("31")
    ).quantize(Decimal("0.0001"))
    # Derived from the fraction the response publishes, not from an unrounded one
    # computed here: a projection a client cannot reproduce from the numbers next
    # to it looks like a mistake in whichever of the two it trusts less.
    assert Decimal(row["projected"]) == (
        Decimal("100.00") / Decimal(forecast["elapsed_fraction"])
    ).quantize(Decimal("0.01"))
    assert Decimal(row["projected"]) == Decimal("206.65")


async def test_a_finished_month_projects_exactly_what_was_spent(client):
    """Nothing left to extrapolate over: the projection is the actual. Without
    clamping the anchor into the month, asking about March in August would have
    scaled March's spending by a fraction of a month that ended long ago."""
    envelope_id = await _create_envelope(client, "Already over")
    await _assign(client, envelope_id, "2026-03-01", "300.00")
    await _spend(client, envelope_id, "2026-03-10", "-120.00")

    forecast = await _forecast(client, month="2026-03-01", asOf="2026-08-08")
    row = _row(forecast, envelope_id)

    assert forecast["as_of"] == "2026-03-31"
    assert Decimal(forecast["elapsed_fraction"]) == Decimal("1.0000")
    assert Decimal(row["projected"]) == Decimal("120.00")


async def test_an_untouched_envelope_projects_nothing(client):
    """A savings envelope with 400 assigned and nothing spent is not forecast to
    spend anything. The mock this replaced guessed `assigned * 0.15`."""
    envelope_id = await _create_envelope(client, "Savings")
    await _assign(client, envelope_id, "2026-03-01", "400.00")

    row = _row(await _forecast(client, month="2026-03-01", asOf="2026-03-15"), envelope_id)

    assert Decimal(row["spent"]) == Decimal("0")
    assert Decimal(row["projected"]) == Decimal("0")


async def test_forecast_measures_against_what_carried_over_too(client):
    """The baseline is what the envelope holds, not this month's top-up alone.

    Assigned 100 in February and spent 40, so 60 carried into March; assigned
    another 50 there. `funded` is 110, and a projection of 100 is inside plan -
    against March's 50 alone it would look like a 50 overshoot.
    """
    envelope_id = await _create_envelope(client, "Carries over")
    await _assign(client, envelope_id, "2026-02-01", "100.00")
    await _spend(client, envelope_id, "2026-02-10", "-40.00")
    await _assign(client, envelope_id, "2026-03-01", "50.00")

    row = _row(await _forecast(client, month="2026-03-01", asOf="2026-03-15"), envelope_id)

    assert Decimal(row["carried_over"]) == Decimal("60.00")
    assert Decimal(row["assigned"]) == Decimal("50.00")
    assert Decimal(row["funded"]) == Decimal("110.00")
    # February's spending belongs to February, not to this month's figure.
    assert Decimal(row["spent"]) == Decimal("0")


async def test_next_months_assignment_does_not_fund_this_month(client):
    envelope_id = await _create_envelope(client, "Funded ahead")
    await _assign(client, envelope_id, "2026-03-01", "50.00")
    await _assign(client, envelope_id, "2026-04-01", "500.00")

    row = _row(await _forecast(client, month="2026-03-01", asOf="2026-03-15"), envelope_id)

    assert Decimal(row["funded"]) == Decimal("50.00")


async def test_uncategorised_spending_is_not_forecast_against_any_envelope(client):
    """A transaction with no envelope cannot be projected onto one. It still left
    the account - `to-assign` accounts for that - but it belongs to no plan."""
    envelope_id = await _create_envelope(client, "Untouched by the import")
    await _assign(client, envelope_id, "2026-03-01", "100.00")
    await _spend(client, None, "2026-03-10", "-70.00")

    row = _row(await _forecast(client, month="2026-03-01", asOf="2026-03-15"), envelope_id)

    assert Decimal(row["spent"]) == Decimal("0")
    assert Decimal(row["projected"]) == Decimal("0")


async def test_income_is_not_spending(client):
    envelope_id = await _create_envelope(client, "Refunded")
    await _assign(client, envelope_id, "2026-03-01", "100.00")
    await _spend(client, envelope_id, "2026-03-05", "-50.00")
    await _spend(client, envelope_id, "2026-03-06", "500.00")

    row = _row(await _forecast(client, month="2026-03-01", asOf="2026-03-15"), envelope_id)

    assert Decimal(row["spent"]) == Decimal("50.00")


async def test_group_rollup_matches_its_envelopes(client):
    """The seeded database has other envelopes in this group, so this asserts the
    group is the sum of the envelopes the forecast itself reports for it, not a
    figure computed from these two alone."""
    first = await _create_envelope(client, "Rollup one")
    second = await _create_envelope(client, "Rollup two")
    await _assign(client, first, "2026-03-01", "100.00")
    await _assign(client, second, "2026-03-01", "200.00")
    await _spend(client, first, "2026-03-10", "-30.00")

    forecast = await _forecast(client, month="2026-03-01", asOf="2026-03-15")
    group = next(
        g
        for g in forecast["category_groups"]
        if g["category_group_id"] == SEEDED_CATEGORY_GROUP_ID
    )
    members = [
        e
        for e in forecast["envelopes"]
        if e["category_group_id"] == SEEDED_CATEGORY_GROUP_ID
    ]

    for field in ("funded", "spent", "projected"):
        assert Decimal(group[field]) == sum(Decimal(e[field]) for e in members)


async def test_totals_match_the_envelope_rows(client):
    forecast = await _forecast(client, month="2026-03-01", asOf="2026-03-15")

    for total, field in (
        ("funded_total", "funded"),
        ("spent_total", "spent"),
        ("projected_total", "projected"),
    ):
        assert Decimal(forecast[total]) == sum(
            Decimal(e[field]) for e in forecast["envelopes"]
        )


async def test_forecast_names_the_estimator_behind_it(client):
    """The screen tells the reader how the numbers were arrived at, so the
    estimator has to be part of the response and not folded into the client."""
    forecast = await _forecast(client, month="2026-03-01", asOf="2026-03-15")

    assert forecast["method"] == "linear-pace"


async def test_most_at_risk_envelope_comes_first(client):
    """Ranked by projected overshoot, by the thing that produced the projection.
    A client re-sorting by its own rule would overrule a model that has a view
    on which risk matters."""
    overspending = await _create_envelope(client, "Zzz runs hot")
    comfortable = await _create_envelope(client, "Aaa is fine")
    await _assign(client, overspending, "2026-03-01", "50.00")
    await _assign(client, comfortable, "2026-03-01", "5000.00")
    await _spend(client, overspending, "2026-03-10", "-200.00")
    await _spend(client, comfortable, "2026-03-10", "-10.00")

    forecast = await _forecast(client, month="2026-03-01", asOf="2026-03-15")
    ranked = [e["envelope_id"] for e in forecast["envelopes"]]

    assert ranked.index(overspending) < ranked.index(comfortable)


async def test_forecast_defaults_to_the_current_month(client):
    """No `month` given answers for the month the user is in - the only thing the
    Forecast screen ever asks for."""
    from datetime import date

    forecast = await _forecast(client)

    assert forecast["month"] == date.today().replace(day=1).isoformat()
    assert forecast["as_of"] == date.today().isoformat()
