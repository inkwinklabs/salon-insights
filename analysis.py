"""
Turns raw visit records into customer facts: visits, average spend, usual
service, and whether someone is a regular, overdue, occasional or one-time.

These rules live in one place so the customer list (stage 3), the dashboard
(stage 4) and the AI summary (stage 5) all agree with each other.

One rule to remember: services on the SAME DAY count as ONE visit.
(A haircut + head massage on Monday is one trip to the salon, not two.)
"""

from collections import Counter
from datetime import date
from statistics import mean


def customer_status(visits: int, days_since: int, avg_gap: float | None, rules: dict) -> str:
    """Which group a customer belongs to.

    rules comes from [reminders] in settings.toml:
      min_visits_for_regular : visits needed to count as a regular
      overdue_factor         : how late (x their usual gap) counts as overdue
    """
    if visits == 1:
        return "one-time"
    if visits < rules["min_visits_for_regular"]:
        return "occasional"
    if avg_gap and days_since > rules["overdue_factor"] * avg_gap:
        return "overdue"
    return "regular"


def customer_stats(customer: dict, lines: list[dict], today: date, rules: dict) -> dict:
    """Facts about one customer from their service lines (one row per service)."""
    dates = sorted({date.fromisoformat(line["visit_date"]) for line in lines})
    visits = len(dates)
    total_spent = sum(line["price"] for line in lines)
    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
    avg_gap = round(mean(gaps)) if gaps else None
    days_since = (today - dates[-1]).days

    # Usual service = the one they have most often. If two are tied,
    # pick the one they had most recently.
    counts = Counter(line["service"] for line in lines)
    latest = {line["service"]: line["visit_date"] for line in lines}  # lines are date-ordered
    usual_service = max(counts, key=lambda s: (counts[s], latest[s]))

    return {
        "id": customer["id"],
        "name": customer["name"],
        "phone": customer["phone"],
        "visits": visits,
        "first_visit": dates[0].isoformat(),
        "last_visit": dates[-1].isoformat(),
        "days_since": days_since,
        "avg_gap": avg_gap,
        "total_spent": total_spent,
        "avg_spend": round(total_spent / visits),
        "usual_service": usual_service,
        "status": customer_status(visits, days_since, avg_gap, rules),
    }


def build_customer_list(rows: list[dict], today: date, rules: dict) -> list[dict]:
    """rows: one per service line, ordered by customer then date (see db.customer_visit_rows)."""
    grouped: dict[int, tuple[dict, list]] = {}
    for row in rows:
        customer, lines = grouped.setdefault(row["id"], (row, []))
        if row["visit_date"]:  # a customer with no visits has an empty row
            lines.append(row)
    return [customer_stats(c, lines, today, rules) for c, lines in grouped.values() if lines]
