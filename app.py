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
from datetime import date

from flask import Flask, jsonify, request, send_from_directory

import db
from analysis import build_customer_list
from scripts.make_demo_data import load_demo_data
from settings import BASE_DIR, load_settings
from validation import normalise_phone, validate_visit

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


# ---------------------------------------------------------------- visits and customers

@app.post("/api/visits")
def api_add_visit():
    """Save a visit from the form. Answers 400 with per-field messages if something's wrong."""
    data = request.get_json() or {}
    phone = normalise_phone(data.get("phone"))
    existing = db.find_customer_by_phone(phone) if phone else None

    clean, errors = validate_visit(
        data, load_settings(), db.get_mode(), date.today(), existing_customer=bool(existing)
    )
    if errors:
        return jsonify(errors=errors), 400
    return jsonify(db.add_visit(clean)), 201


@app.get("/api/customers")
def api_customers():
    """Every customer with their stats (visits, last visit, average spend, status...)."""
    settings = load_settings()
    customers = build_customer_list(db.customer_visit_rows(), date.today(), settings["reminders"])
    return jsonify(customers=customers, rules=settings["reminders"])


@app.get("/api/customers/lookup")
def api_customer_lookup():
    """Used by the form: is this phone number an existing customer?"""
    phone = normalise_phone(request.args.get("phone"))
    if not phone:
        return jsonify(found=False, valid=False)
    customer = db.find_customer_by_phone(phone)
    if not customer:
        return jsonify(found=False, valid=True)
    return jsonify(found=True, valid=True, **customer)


@app.get("/api/customers/<int:customer_id>/visits")
def api_customer_visits(customer_id):
    """One customer's visit history, newest first."""
    return jsonify(visits=db.visits_for_customer(customer_id))


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
