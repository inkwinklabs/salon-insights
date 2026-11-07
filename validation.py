"""
Checks what someone typed into the visit form before it is saved.

Why check on the server when the form already checks? The form's checks are
for convenience; anything sent to the server could skip them. The server is
the last line of defence, so the real rules live here.
"""

import re
from datetime import date

MAX_NAME_LENGTH = 60
MAX_PRICE = 100_000  # rupees; anything bigger is surely a typing mistake


def normalise_phone(raw) -> str | None:
    """Turn '+91 98450-12345', '098450 12345' etc. into '9845012345'.

    Returns None if it isn't 10 digits after tidying.
    """
    digits = re.sub(r"\D", "", str(raw or ""))  # keep digits only
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]          # drop the India country code
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]          # drop a leading 0
    return digits if len(digits) == 10 else None


def phone_problem(phone: str | None, mode: str) -> str | None:
    """Explain what's wrong with a (normalised) phone number, or None if it's fine."""
    if phone is None:
        return "Enter a 10-digit mobile number."
    if mode == "demo" and not phone.startswith("5"):
        # Keeps demo data safe: a WhatsApp link can never reach a real person.
        return "Demo mode: use a made-up number starting with 5, so no real person can be messaged."
    if mode == "real" and phone[0] not in "6789":
        return "Indian mobile numbers start with 6, 7, 8 or 9."
    return None


def validate_visit(data: dict, settings: dict, mode: str, today: date,
                   existing_customer: bool) -> tuple[dict, dict]:
    """Check a visit from the form.

    Returns (clean, errors):
      clean  : the tidied values, ready to save
      errors : {field name: message}; empty means everything is fine
    """
    clean, errors = {}, {}

    # Phone
    phone = normalise_phone(data.get("phone"))
    problem = phone_problem(phone, mode)
    if problem:
        errors["phone"] = problem
    clean["phone"] = phone

    # Name: only needed for a new customer (a returning one keeps their saved name)
    name = " ".join(str(data.get("name") or "").split())  # trim and squash extra spaces
    if not existing_customer:
        if not name:
            errors["name"] = "Enter the customer's name."
        elif len(name) > MAX_NAME_LENGTH:
            errors["name"] = f"Name is too long (max {MAX_NAME_LENGTH} characters)."
    clean["name"] = name

    # Service: must be one listed in settings.toml
    service_names = [s["name"] for s in settings["services"]]
    service = data.get("service")
    if service not in service_names:
        errors["service"] = "Choose a service from the list."
    clean["service"] = service

    # Price: a whole number of rupees
    try:
        price = int(str(data.get("price")).strip())
        if not 0 <= price <= MAX_PRICE:
            raise ValueError
        clean["price"] = price
    except ValueError:
        errors["price"] = f"Enter a price in whole rupees (0 to {MAX_PRICE:,})."

    # Date: a real date, and not in the future
    try:
        visit_date = date.fromisoformat(str(data.get("visit_date")))
        if visit_date > today:
            errors["visit_date"] = "The visit date can't be in the future."
        clean["visit_date"] = visit_date.isoformat()
    except ValueError:
        errors["visit_date"] = "Choose the visit date."

    # Staff: must be one listed in settings.toml
    staff = data.get("staff")
    if staff not in settings["salon"]["staff"]:
        errors["staff"] = "Choose who did the service."
    clean["staff"] = staff

    return clean, errors
