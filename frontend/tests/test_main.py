import flet.testing as ftt


async def test_navigate_to_accounts_and_back(flet_app: ftt.FletTestApp):
    """Routing sample: tap "Accounts" and confirm the Accounts view renders.

    The `flet_app` fixture is provided automatically by the flet pytest plugin.
    Run with `flet test` (or `uv run pytest`) from the project directory.
    """
    tester = flet_app.tester

    await tester.pump_and_settle()

    assert (await tester.find_by_text("Envelo")).count == 1

    await tester.tap(await tester.find_by_text("Accounts"))
    await tester.pump_and_settle()

    assert (await tester.find_by_text("Accounts")).count == 1
    assert (
        await tester.find_by_text(
            "Accounts screen placeholder - budget data lands in a later issue."
        )
    ).count == 1
