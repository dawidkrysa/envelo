import os

API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL", "http://localhost:8000")

# Which Flutter web renderer the browser uses: "auto" (skwasm in Chromium, since
# this flet-web build ships WebAssembly), "canvaskit" or "skwasm". A setting,
# not a constant, because the trade-off is measured, not reasoned: skwasm draws
# animation frames faster, CanvasKit moves the bytes Flet sends on every UI
# update across the JS/Dart boundary faster. Which feels smoother depends on
# the machine and browser, so it is switchable without a code change.
WEB_RENDERER = os.environ.get("FLET_WEB_RENDERER", "auto")
