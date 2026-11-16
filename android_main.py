"""
Start-up for the Android app. The laptop never uses this file.

The Android app is a thin shell: a full-screen web view (the same screens as
on the laptop) plus this same Python server running quietly inside the app.
MainActivity.kt calls start() once when the app opens.

What is different on a phone, and why:
  - Data goes to the app's private storage, which other apps can't read.
  - There is no .env file, so the API key is typed into the app and locked
    away by Android (KeyVault.kt). start() receives it and keeps it in memory.
  - Every app on a phone can reach 127.0.0.1, so the server only answers
    requests that carry this run's random pass-code (see app.py).
"""

import os
import secrets
import socket
import threading


def free_port() -> int:
    """Ask Android for any unused port, so we never clash with another app."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(data_dir: str, saved_api_key: str) -> list:
    """Start the server in the background. Returns [port, pass-code] for the screen."""
    token = secrets.token_urlsafe(32)
    os.environ["SALON_ON_PHONE"] = "1"
    os.environ["SALON_DATA_DIR"] = data_dir
    os.environ["SALON_APP_TOKEN"] = token
    if saved_api_key:
        os.environ["ANTHROPIC_API_KEY"] = saved_api_key

    # Imported only now, because app.py reads the settings above as it loads.
    from waitress import serve
    from app import app

    port = free_port()
    threading.Thread(
        target=lambda: serve(app, host="127.0.0.1", port=port, threads=4, _quiet=True),
        name="salon-server", daemon=True,
    ).start()
    return [port, token]


def save_api_key(key: str) -> None:
    """Lock the key away with Android's Keystore, and start using it right away."""
    from com.inkwinklabs.salon import KeyVault   # the Kotlin class, reached from Python
    KeyVault.save(key)
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key
    else:
        os.environ.pop("ANTHROPIC_API_KEY", None)
