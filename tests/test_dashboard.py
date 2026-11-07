"""
Tests for stage 4: the dashboard numbers.

Small hand-made data, so the right answers can be worked out on paper.
"""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import build_dashboard  # noqa: E402
from app import app  # noqa: E402
from tests.test_visits_and_customers import use_temporary_databases  # noqa: E402

TODAY = date(2026, 11, 7)  # a Saturday


def line(customer_id, day, service, price):
    return {"customer_id": customer_id, "visit_date": day, "service": service, "price": price}


LINES = [
    # Customer 1: a regular. Two services on 3 Nov count as ONE visit.
    line(1, "2026-09-15", "Haircut", 300),     # Tuesday
    line(1, "2026-10-13", "Haircut", 300),     # Tuesday
    line(1, "2026-11-03", "Haircut", 300),     # Tuesday
    line(1, "2026-11-03", "Head Massage", 350),
    # Customer 2: one visit only.
    line(2, "2026-11-07", "Facial", 1200),     # Saturday
    # Customer 3: came long ago, then in this period.
    line(3, "2026-05-10", "Beard Trim", 150),  # Sunday
    line(3, "2026-11-01", "Beard Trim", 150),  # Sunday
]


class DashboardTests(unittest.TestCase):
    def board(self, period):
        # Fresh copies each time, because build_dashboard adds a "day" field.
        return build_dashboard([dict(l) for l in LINES], TODAY, period, overdue_now=4)

    def test_all_time_totals(self):
        k = self.board("all")["kpis"]
        self.assertEqual(k["customers"], 3)
        self.assertEqual(k["visits"], 6)          # 7 service lines, but 3 Nov is one visit
        self.assertEqual(k["revenue"], 2750)
        self.assertEqual(k["avg_spend_per_visit"], round(2750 / 6))
        self.assertEqual(k["repeat_customers"], 2)
        self.assertEqual(k["one_time_customers"], 1)
        self.assertEqual(k["overdue_now"], 4)

    def test_last_30_days(self):
        d = self.board("30")
        self.assertEqual(d["period"]["start"], "2026-10-09")
        k = d["kpis"]
        self.assertEqual(k["customers"], 3)       # all three came since 9 Oct
        self.assertEqual(k["visits"], 4)          # 13 Oct, 3 Nov, 7 Nov, 1 Nov
        self.assertEqual(k["revenue"], 300 + 650 + 1200 + 150)
        # Customer 3 counts as repeat: they also came in May, before the period.
        self.assertEqual(k["repeat_customers"], 2)
        self.assertEqual(k["new_customers"], 1)   # only customer 2 first came in the period

    def test_weekdays_count_visits_not_services(self):
        days = {d["day"]: d for d in self.board("all")["weekdays"]}
        self.assertEqual(days["Tue"]["visits"], 3)  # 3 Nov had 2 services but is 1 visit
        self.assertEqual(days["Tue"]["revenue"], 1250)
        self.assertEqual(days["Sat"]["visits"], 1)
        self.assertEqual(days["Sun"]["visits"], 2)
        self.assertEqual(days["Mon"]["visits"], 0)

    def test_services_ranked_by_revenue(self):
        services = self.board("all")["services"]
        self.assertEqual(services[0], {"service": "Facial", "count": 1, "revenue": 1200, "avg_price": 1200})
        self.assertEqual(services[1]["service"], "Haircut")
        self.assertEqual(services[1]["count"], 3)

    def test_part_months_are_flagged(self):
        months = self.board("all")["months"]
        self.assertEqual([m["month"] for m in months][0], "2026-05")
        self.assertEqual(len(months), 7)            # May to Nov, including empty months
        self.assertTrue(months[0]["partial"])       # data starts 10 May
        self.assertFalse(months[4]["partial"])      # September is complete
        self.assertTrue(months[-1]["partial"])      # November so far
        self.assertEqual(months[-1]["covered_to"], "2026-11-07")
        self.assertEqual(months[1]["revenue"], 0)   # June: nothing, but still shown

    def test_no_data(self):
        d = build_dashboard([], TODAY, "all", overdue_now=0)
        self.assertEqual(d["kpis"]["visits"], 0)
        self.assertEqual(d["kpis"]["avg_spend_per_visit"], 0)
        self.assertEqual(len(d["months"]), 1)

    def test_unknown_period(self):
        with self.assertRaises(ValueError):
            build_dashboard([], TODAY, "7", overdue_now=0)


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        use_temporary_databases(self)
        self.client = app.test_client()

    def test_empty_dashboard_and_bad_period(self):
        r = self.client.get("/api/dashboard?period=90")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["kpis"]["visits"], 0)
        self.assertEqual(self.client.get("/api/dashboard?period=7").status_code, 400)

    def test_dashboard_sends_no_names_or_phones(self):
        self.client.post("/api/visits", json={
            "phone": "9845012345", "name": "Test Person", "service": "Haircut",
            "price": 300, "visit_date": date.today().isoformat(), "staff": "Ravi"})
        text = self.client.get("/api/dashboard").get_data(as_text=True)
        self.assertNotIn("Test Person", text)
        self.assertNotIn("9845012345", text)


if __name__ == "__main__":
    unittest.main()
