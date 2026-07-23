"""Container/production entrypoint - served by uvicorn, not `flet run`.

`main.py` stays a normal Flet script (`if __name__ == "__main__": ft.run(main)`)
so `flet run` / `flet test` / `flet build` keep working unmodified. This module
exists only to expose the ASGI app export_asgi_app=True returns, which uvicorn
needs to be able to `import asgi:app`.
"""

import flet as ft
from main import main

app = ft.run(main, export_asgi_app=True)
