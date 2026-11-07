"""
The web server for Salon Customer Insights.

How it works:
  - The browser asks for "/" and gets static/index.html (the screens).
  - The screens then ask for data at addresses starting with "/api/".
    Those answers are JSON (plain structured text), never HTML.

Keeping the screens and the data separate like this means the same /api
could later serve an Android app or an online version.

Start it with:  python3 start.py
"""

import sys
import threading
import tomllib
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "settings.toml"
STATIC_DIR = BASE_DIR / "static"


def load_settings() -> dict:
    """Read settings.toml. We read it fresh each time so edits show up after a restart."""
    with open(SETTINGS_FILE, "rb") as f:
        return tomllib.load(f)


app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")


@app.get("/")
def home():
    """Send the main page. Everything else on screen is filled in by static/app.js."""
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/settings")
def api_settings():
    """Salon name, staff and services, so the screens never hard-code them.

    We hand-pick what to send rather than sending the whole file, so nothing
    private can leak out by accident if more settings are added later.
    """
    s = load_settings()
    return jsonify(
        salon=s["salon"],
        services=s["services"],
        ai_model=s["ai"]["model"],
    )


@app.get("/api/health")
def api_health():
    """A tiny "are you alive?" check, handy for testing."""
    return jsonify(ok=True)


if __name__ == "__main__":
    settings = load_settings()
    port = settings["app"]["port"]
    url = f"http://127.0.0.1:{port}"

    print(f"\n  {settings['salon']['name']} | Customer Insights")
    print(f"  Open {url} in your browser. Press Ctrl+C to stop.\n")

    if "--no-browser" not in sys.argv:
        # Open the browser a moment after the server has started.
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # host="127.0.0.1" means only this laptop can open the app. Other phones or
    # computers on the same Wi-Fi cannot, which keeps customer data private.
    app.run(host="127.0.0.1", port=port, debug=False)
