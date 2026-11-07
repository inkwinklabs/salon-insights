"""
Turns raw visit records into customer facts: visits, average spend, usual
service, and whether someone is a regular, overdue, occasional or one-time.

These rules live in one place so the customer list (stage 3), the dashboard
(stage 4) and the AI summary (stage 5) all agree with each other.

One rule to remember: services on the SAME DAY count as ONE visit.
(A haircut + head massage on Monday is one trip to the salon, not two.)
"""

from collections import Counter
from datetime import date, timedelta
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


# ================================================================ dashboard

# The period choices on the dashboard: key → (label, number of days).
# None means "everything we have".
PERIODS = {
    "30": ("Last 30 days", 30),
    "90": ("Last 90 days", 90),
    "182": ("Last 6 months", 182),
    "all": ("All time", None),
}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def period_range(period: str, today: date, first_visit: date | None) -> tuple[date, date]:
    """First and last day (both included) of the chosen period."""
    days = PERIODS[period][1]
    if days is None:
        return (first_visit or today), today
    return today - timedelta(days=days - 1), today


def month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    next_first = date(year + (month == 12), month % 12 + 1, 1)
    return first, next_first - timedelta(days=1)


def build_dashboard(lines: list[dict], today: date, period: str, overdue_now: int) -> dict:
    """All the dashboard numbers for one period.

    lines: one row per service (customer_id, visit_date, service, price), see db.visit_lines().
    overdue_now: how many regulars are overdue today (from build_customer_list).

    Reminder: services on the same day by the same customer count as ONE visit.
    """
    if period not in PERIODS:
        raise ValueError(f"Unknown period {period!r}")

    for line in lines:
        line["day"] = date.fromisoformat(line["visit_date"])
    first_visit = min((l["day"] for l in lines), default=None)
    start, end = period_range(period, today, first_visit)
    in_period = [l for l in lines if start <= l["day"] <= end]

    # A "visit" = one customer on one day.
    visits = {(l["customer_id"], l["day"]) for l in in_period}
    revenue = sum(l["price"] for l in in_period)

    # Repeat vs one-time, for the customers who came in this period:
    # "repeat" = has come on 2 or more different days (up to the end of the period).
    days_per_customer: dict[int, set] = {}
    first_day: dict[int, date] = {}
    for l in lines:
        if l["day"] <= end:
            days_per_customer.setdefault(l["customer_id"], set()).add(l["day"])
            first_day[l["customer_id"]] = min(first_day.get(l["customer_id"], l["day"]), l["day"])
    customers = {cid for cid, _ in visits}
    repeat = sum(1 for cid in customers if len(days_per_customer[cid]) >= 2)

    # Busiest days of the week (visits), plus revenue for the tooltip and table.
    weekday_visits = Counter(day.weekday() for _, day in visits)
    weekday_revenue = Counter()
    for l in in_period:
        weekday_revenue[l["day"].weekday()] += l["price"]

    # Services: how many times each was done, what it earned, average price.
    service_count, service_revenue = Counter(), Counter()
    for l in in_period:
        service_count[l["service"]] += 1
        service_revenue[l["service"]] += l["price"]
    services = sorted(
        (
            {"service": s, "count": service_count[s], "revenue": service_revenue[s],
             "avg_price": round(service_revenue[s] / service_count[s])}
            for s in service_count
        ),
        key=lambda s: s["revenue"],
        reverse=True,
    )

    # Monthly revenue. A month is a "part month" if the period doesn't cover
    # all of it (e.g. the current month so far), so it isn't mistaken for a slump.
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        first, last = month_bounds(year, month)
        in_month = [l for l in in_period if first <= l["day"] <= last]
        months.append({
            "month": f"{year}-{month:02d}",
            "revenue": sum(l["price"] for l in in_month),
            "visits": len({(l["customer_id"], l["day"]) for l in in_month}),
            "partial": first < start or last > end,
            "covered_from": max(first, start).isoformat(),
            "covered_to": min(last, end).isoformat(),
        })
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)

    return {
        "period": {"key": period, "label": PERIODS[period][0],
                   "start": start.isoformat(), "end": end.isoformat()},
        "kpis": {
            "customers": len(customers),
            "new_customers": sum(1 for cid in customers if first_day[cid] >= start),
            "repeat_customers": repeat,
            "one_time_customers": len(customers) - repeat,
            "visits": len(visits),
            "revenue": revenue,
            "avg_spend_per_visit": round(revenue / len(visits)) if visits else 0,
            "overdue_now": overdue_now,
        },
        "weekdays": [
            {"day": WEEKDAYS[i], "visits": weekday_visits[i], "revenue": weekday_revenue[i]}
            for i in range(7)
        ],
        "services": services,
        "months": months,
    }
