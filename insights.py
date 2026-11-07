"""
AI insights: the only part of the app that sends anything off the laptop.

How it stays private, step by step:
  1. build_ai_summary() makes a summary of NUMBERS ONLY: counts, totals,
     averages, days since last visit. No customer names, no phone numbers,
     no staff names.
  2. check_no_personal_data() double-checks the finished text before it is
     sent. If any customer's name or phone number (or any 10-digit number)
     is found, it refuses to send. This is a safety net in case a future
     code change makes a mistake.
  3. Claude replies with insights and a WhatsApp message TEMPLATE with
     blanks like {name}. The app fills in the blanks later, on the laptop.

The API key is read from the ANTHROPIC_API_KEY setting in the .env file.
It is never printed, logged or shown.
"""

import json
import os
import re
from datetime import date, datetime

import anthropic

import db
from analysis import build_customer_list, build_dashboard

# Blanks a reminder template may use. The app fills them in locally.
TEMPLATE_BLANKS = {"name", "service", "salon", "days"}
MAX_TEMPLATE_LENGTH = 600

# Models that accept the server-side "fallbacks" option (see ask_claude).
MODELS_WITH_FALLBACK = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}


class InsightsError(Exception):
    """A problem we can explain to the salon owner in plain words."""


class PrivacyError(InsightsError):
    """The summary contained personal data, so it was NOT sent."""


# ================================================================ 1. the summary

def build_ai_summary(today: date, settings: dict) -> tuple[dict, list[dict]]:
    """Numbers-only summary for the AI, plus the customer list (kept LOCAL for the privacy check)."""
    rules = settings["reminders"]
    customers = build_customer_list(db.customer_visit_rows(), today, rules)
    overdue = [c for c in customers if c["status"] == "overdue"]

    all_time = build_dashboard(db.visit_lines(), today, "all", overdue_now=len(overdue))
    last_30 = build_dashboard(db.visit_lines(), today, "30", overdue_now=len(overdue))

    gap_by_service = {s["name"]: s["typical_gap_days"] for s in settings["services"]}
    list_price = {s["name"]: s["price"] for s in settings["services"]}

    groups: dict[str, int] = {}
    for c in customers:
        groups[c["status"]] = groups.get(c["status"], 0) + 1

    one_time_by_service: dict[str, int] = {}
    for c in customers:
        if c["status"] == "one-time":
            one_time_by_service[c["usual_service"]] = one_time_by_service.get(c["usual_service"], 0) + 1

    summary = {
        "about": {
            "business": "a small hair salon and barbershop in India",
            "city": settings["salon"].get("city", ""),
            "currency": "INR (₹)",
            "today": today.isoformat(),
            "data_from": all_time["period"]["start"],
            "data_to": all_time["period"]["end"],
        },
        "definitions": {
            "visit": "one customer on one day (several services that day = one visit)",
            "regular": f"{rules['min_visits_for_regular']}+ visits",
            "overdue": f"a regular whose days since last visit is more than "
                       f"{rules['overdue_factor']}x their own usual gap between visits",
            "partial_month": "a month only partly covered by the data (the first month, "
                             "or the current month so far); not a real drop",
            "totals.customers": "different customers who visited in that period",
            "totals.new_customers": "of those, how many visited for the very first time in that period",
            "totals.repeat_customers": "of those, how many have visited on 2+ different days in total",
            "totals.one_time_customers": "of those, how many have visited only once in total",
            "totals.avg_spend_per_visit": "revenue divided by visits",
        },
        "totals_all_time": _totals(all_time["kpis"]),
        "totals_last_30_days": _totals(last_30["kpis"]),
        "visits_by_weekday_all_time": all_time["weekdays"],
        "services_all_time": [
            {**s, "list_price": list_price.get(s["service"]),
             "typical_return_gap_days": gap_by_service.get(s["service"])}
            for s in all_time["services"]
        ],
        "monthly": [
            {"month": m["month"], "revenue": m["revenue"], "visits": m["visits"], "partial_month": m["partial"]}
            for m in all_time["months"]
        ],
        "customer_groups": groups,
        # One anonymous row per overdue regular: no name, no phone, no id.
        "overdue_regulars": [
            {"usual_service": c["usual_service"], "visits": c["visits"],
             "usual_gap_days": c["avg_gap"], "days_since_last_visit": c["days_since"],
             "avg_spend_per_visit": c["avg_spend"]}
            for c in sorted(overdue, key=lambda c: -c["days_since"])
        ],
        "one_time_customers_by_service": one_time_by_service,
    }
    return summary, customers


def _totals(kpis: dict) -> dict:
    return {k: v for k, v in kpis.items() if k != "overdue_now"}


# ================================================================ 2. the privacy check

def summary_as_text(summary: dict) -> str:
    """The exact text that is sent (and shown in the preview)."""
    return json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True)


def check_no_personal_data(text: str, customers: list[dict]) -> None:
    """Refuse to send if any customer's name or phone, or any 10-digit number, is in the text."""
    lowered = text.lower()
    for c in customers:
        if c["phone"] and c["phone"] in text:
            raise PrivacyError("Stopped: a customer phone number was found in the summary. Nothing was sent.")
        if c["name"] and c["name"].lower() in lowered:
            raise PrivacyError("Stopped: a customer name was found in the summary. Nothing was sent.")
    if re.search(r"\d{10}", text):
        raise PrivacyError("Stopped: something that looks like a phone number was found. Nothing was sent.")


# ================================================================ 3. asking Claude

SYSTEM_PROMPT = """You are a friendly, practical business advisor for a small salon and barbershop in India.
You receive an aggregated summary of the salon's records. It has no customer names or contact details.

Write insights the owner can act on this week:
- Base every insight on numbers in the summary, and quote the specific numbers.
- Use plain, simple English with no business jargon. Write money as ₹ with Indian digit grouping (₹1,61,040).
- Months marked partial_month only cover part of that month, so never describe them as a drop.
- Give 3 to 6 insights, most valuable first. Each has a short title, what the data shows, and one concrete action.
- Cover, where the data supports it: overdue regulars, the quietest and busiest days, which services earn the most per visit and in total, one-time customers who never returned, and the revenue trend.

Also write one WhatsApp reminder message template for overdue regular customers, in {language}:
- Warm, short (under 300 characters), personal, no pressure.
- Use these blanks exactly as written: {{name}} for the customer's first name, {{service}} for their usual service, {{salon}} for the salon name. {{days}} (days since their last visit) is optional.
- Do not add any other blanks, links, phone numbers, prices or discounts."""

INSIGHTS_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "One sentence: the single most important takeaway."},
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "finding": {"type": "string", "description": "What the numbers show."},
                    "action": {"type": "string", "description": "One concrete thing to do."},
                    "topic": {"type": "string", "enum": ["retention", "scheduling", "services", "revenue", "growth"]},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["title", "finding", "action", "topic", "priority"],
                "additionalProperties": False,
            },
        },
        "reminder_template": {"type": "string"},
    },
    "required": ["headline", "insights", "reminder_template"],
    "additionalProperties": False,
}


def ask_claude(summary_text: str, settings: dict) -> dict:
    """Send the (already checked) summary to Claude and return its parsed reply."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise InsightsError("No API key found. Put ANTHROPIC_API_KEY=... in the .env file "
                            "(see .env.example), then restart the app.")
    ai = settings["ai"]
    request = {
        "model": ai["model"],
        "max_tokens": ai["max_tokens"],
        "output_config": {
            "effort": ai.get("effort", "medium"),
            # Structured output: the reply is guaranteed to match INSIGHTS_SCHEMA.
            "format": {"type": "json_schema", "schema": INSIGHTS_SCHEMA},
        },
        "system": SYSTEM_PROMPT.format(language=ai.get("message_language", "English")),
        "messages": [{"role": "user", "content": "Here is the salon summary as JSON:\n\n" + summary_text}],
    }
    # If a safety check wrongly declines the request, "fallbacks" lets the API
    # retry it on another model automatically. Only some models accept it.
    if ai["model"] in MODELS_WITH_FALLBACK:
        request["betas"] = ["server-side-fallback-2026-07-01"]
        request["fallbacks"] = "default"

    client = anthropic.Anthropic(timeout=180.0)  # reads ANTHROPIC_API_KEY itself
    try:
        response = client.beta.messages.create(**request)
    except anthropic.AuthenticationError:
        raise InsightsError("The API key in .env was not accepted. Check it, then restart the app.")
    except anthropic.PermissionDeniedError:
        raise InsightsError("This API key isn't allowed to use that model.")
    except anthropic.NotFoundError:
        raise InsightsError(f"Model {ai['model']!r} was not found. Check [ai] model in settings.toml.")
    except anthropic.RateLimitError:
        raise InsightsError("Too many requests just now. Wait a minute and try again.")
    except anthropic.BadRequestError as e:
        raise InsightsError(f"The AI service rejected the request: {e.message}")
    except anthropic.APIStatusError as e:
        raise InsightsError(f"The AI service had a problem (error {e.status_code}). Try again later.")
    except anthropic.APIConnectionError:
        raise InsightsError("Couldn't reach the AI service. Check the internet connection.")

    if response.stop_reason == "refusal":
        raise InsightsError("The AI declined this request. Try again, or change the model in settings.toml.")
    if response.stop_reason == "max_tokens":
        raise InsightsError("The AI's reply was cut off. Raise [ai] max_tokens in settings.toml.")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise InsightsError("The AI sent an empty reply. Please try again.")
    try:
        reply = json.loads(text)
    except json.JSONDecodeError:
        raise InsightsError("The AI's reply couldn't be read. Please try again.")
    reply["model"] = response.model
    reply["usage"] = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    return reply


# ================================================================ 4. the reminder template

def clean_template(template: str, default: str) -> tuple[str, str | None]:
    """Use the AI's template only if it's safe and fillable; otherwise the default.

    Returns (template, note). note explains why the default was used, or None.
    """
    template = (template or "").strip()
    blanks = set(re.findall(r"\{(\w+)\}", template))
    if not template:
        return default, "The AI didn't write a reminder, so the default one is used."
    if "name" not in blanks:
        return default, "The AI's reminder had no {name} blank, so the default one is used."
    if blanks - TEMPLATE_BLANKS:
        return default, "The AI's reminder had unknown blanks, so the default one is used."
    if len(template) > MAX_TEMPLATE_LENGTH or re.search(r"https?://|www\.", template, re.I):
        return default, "The AI's reminder was too long or had a link, so the default one is used."
    return template, None


# ================================================================ 5. putting it together

def results_file():
    """Last result, saved separately for real and demo data (data/ is never committed)."""
    return db.DATA_DIR / f"insights-{db.get_mode()}.json"


def generate_insights(settings: dict, today: date | None = None) -> dict:
    today = today or date.today()
    summary, customers = build_ai_summary(today, settings)
    if not customers:
        raise InsightsError("There's no data yet. Log some visits (or load the demo data) first.")
    text = summary_as_text(summary)
    check_no_personal_data(text, customers)   # stops here if anything personal slipped in

    reply = ask_claude(text, settings)
    template, note = clean_template(reply.get("reminder_template", ""),
                                    settings["reminders"]["default_template"])
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": reply["model"],
        "headline": reply.get("headline", ""),
        "insights": reply.get("insights", []),
        "reminder_template": template,
        "template_note": note,
        "usage": reply["usage"],
        "summary_characters_sent": len(text),
    }
    db.DATA_DIR.mkdir(exist_ok=True)
    results_file().write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def last_insights() -> dict | None:
    try:
        return json.loads(results_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
