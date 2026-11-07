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

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import db
import insights
from analysis import PERIODS, build_customer_list, build_dashboard
from scripts.make_demo_data import load_demo_data
from settings import BASE_DIR, load_settings
from validation import normalise_phone, validate_visit

STATIC_DIR = BASE_DIR / "static"

# Read ANTHROPIC_API_KEY from the .env file into this program's settings.
# (It is only ever passed to the Anthropic library, never printed or shown.)
load_dotenv(BASE_DIR / ".env")

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


@app.get("/api/dashboard")
def api_dashboard():
    """Dashboard numbers for one period: ?period=30 | 90 | 182 | all (default all)."""
    period = request.args.get("period", "all")
    if period not in PERIODS:
        return jsonify(error="period must be one of: " + ", ".join(PERIODS)), 400
    today = date.today()
    settings = load_settings()
    customers = build_customer_list(db.customer_visit_rows(), today, settings["reminders"])
    overdue_now = sum(1 for c in customers if c["status"] == "overdue")
    result = build_dashboard(db.visit_lines(), today, period, overdue_now)
    result["periods"] = [{"key": k, "label": label} for k, (label, _) in PERIODS.items()]
    return jsonify(result)


# ---------------------------------------------------------------- AI insights

@app.get("/api/insights/preview")
def api_insights_preview():
    """Exactly what WOULD be sent to the AI, so the owner can check it. Nothing is sent."""
    settings = load_settings()
    summary, customers = insights.build_ai_summary(date.today(), settings)
    text = insights.summary_as_text(summary)
    try:
        insights.check_no_personal_data(text, customers)
        safe = True
    except insights.PrivacyError:
        safe = False
    ai = settings["ai"]
    return jsonify(
        model=ai["model"],
        instructions=insights.SYSTEM_PROMPT.format(language=ai.get("message_language", "English")),
        summary=text,
        passed_privacy_check=safe,
    )


@app.get("/api/insights")
def api_last_insights():
    """The last saved insights for this mode (no AI call, so no cost)."""
    return jsonify(result=insights.last_insights())


@app.post("/api/insights")
def api_generate_insights():
    """Build the numbers-only summary, check it, send it to Claude, save the answer."""
    try:
        return jsonify(result=insights.generate_insights(load_settings()))
    except insights.InsightsError as e:
        return jsonify(error=str(e)), 503


@app.get("/api/reminders")
def api_reminders():
    """Overdue regulars + the message template. Names stay on this laptop."""
    settings = load_settings()
    customers = build_customer_list(db.customer_visit_rows(), date.today(), settings["reminders"])
    last_opened = db.last_reminder_dates()
    saved = insights.last_insights()
    template = saved["reminder_template"] if saved else settings["reminders"]["default_template"]
    overdue = sorted((c for c in customers if c["status"] == "overdue"), key=lambda c: -c["days_since"])
    return jsonify(
        mode=db.get_mode(),
        salon=settings["salon"]["name"],
        template=template,
        template_source="ai" if saved else "default",
        default_template=settings["reminders"]["default_template"],
        customers=[
            {"id": c["id"], "name": c["name"], "phone": c["phone"], "usual_service": c["usual_service"],
             "days_since": c["days_since"], "avg_gap": c["avg_gap"], "visits": c["visits"],
             "last_reminder": last_opened.get(c["id"])}
            for c in overdue
        ],
    )


@app.post("/api/reminders/<int:customer_id>/opened")
def api_reminder_opened(customer_id):
    """Remember that a WhatsApp reminder was opened for this customer."""
    if not db.log_reminder_opened(customer_id):
        return jsonify(error="No such customer"), 404
    return jsonify(ok=True)


@app.get("/api/customers/<int:customer_id>/visits")
def api_customer_visits(customer_id):
    """One customer's visit history, newest first."""
    return jsonify(visits=db.visits_for_customer(customer_id))


def port_is_free(port: int) -> bool:
    """True if nothing else on this laptop is using the port yet."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


if __name__ == "__main__":
    settings = load_settings()
    port = settings["app"]["port"]
    url = f"http://127.0.0.1:{port}"
    open_browser = "--no-browser" not in sys.argv

    if not port_is_free(port):
        # Usually means the app is already running (e.g. start.bat clicked twice).
        print(f"\n  The app seems to be running already. Open {url}", flush=True)
        print(f"  (If it isn't, another program is using port {port}: change [app] port in settings.toml.)\n", flush=True)
        if open_browser:
            webbrowser.open(url)
        sys.exit(0)

    print(f"\n  {settings['salon']['name']} | Customer Insights", flush=True)
    print(f"  Open {url} in your browser. Press Ctrl+C to stop.\n", flush=True)

    if open_browser:
        # Open the browser a moment after the server has started.
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # Waitress is a small, reliable web server written in Python (it works the
    # same on Windows). Flask's own server is only meant for development.
    # host="127.0.0.1" means only this laptop can open the app. Other phones or
    # computers on the same Wi-Fi cannot, which keeps customer data private.
    from waitress import serve
    serve(app, host="127.0.0.1", port=port, threads=4, _quiet=True)
