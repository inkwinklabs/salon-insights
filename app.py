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
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

import db
from scripts.make_demo_data import load_demo_data
from settings import BASE_DIR, load_settings

STATIC_DIR = BASE_DIR / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")


@app.before_request
def only_json_for_changes():
    """Requests that CHANGE something (POST) must be sent as JSON.

    Why: a web browser won't let some other website send JSON to this app
    without permission, so a random page you visit can't press our buttons
    (for example "clear data") behind your back. Our own screens always send JSON.
    """
    if request.method == "POST" and not request.is_json:
        return jsonify(error="Please send JSON"), 415


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


# ---------------------------------------------------------------- demo / real mode

@app.get("/api/mode")
def api_get_mode():
    return jsonify(mode=db.get_mode())


@app.post("/api/mode")
def api_set_mode():
    """Switch between real data (salon.db) and demo data (demo.db)."""
    mode = (request.get_json() or {}).get("mode")
    if mode not in db.DB_FILES:
        return jsonify(error="mode must be 'real' or 'demo'"), 400
    db.set_mode(mode)
    return jsonify(mode=mode)


@app.post("/api/demo/load")
def api_demo_load():
    """Switch to demo mode and fill demo.db with fresh sample data."""
    db.set_mode("demo")
    result = load_demo_data()
    return jsonify(mode="demo", **result)


@app.post("/api/demo/clear")
def api_demo_clear():
    """Empty demo.db. The real data is never touched by this."""
    db.clear_demo()
    return jsonify(ok=True)


@app.get("/api/summary")
def api_summary():
    """Headline numbers for whichever data (real or demo) is active."""
    return jsonify(mode=db.get_mode(), **db.summary_counts())


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
