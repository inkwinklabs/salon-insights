"""
Tests for stage 3: checking form input, saving visits, and the customer list.

Run them with:   .venv/bin/python -m unittest      (Windows: .venv\\Scripts\\python -m unittest)

Each test uses a brand-new temporary folder for its databases, so tests can
never touch your real data (salon.db) or your demo data (demo.db).
"""

import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from analysis import build_customer_list, customer_status  # noqa: E402
from app import app  # noqa: E402
from settings import load_settings  # noqa: E402
from validation import normalise_phone, validate_visit  # noqa: E402

RULES = {"min_visits_for_regular": 3, "overdue_factor": 1.5}
TODAY = date.today()


def use_temporary_databases(test: unittest.TestCase) -> None:
    """Point db.py at a throwaway folder for the length of one test."""
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    data = Path(folder.name)
    originals = (db.DATA_DIR, db.REAL_DB, db.DEMO_DB, db.MODE_FILE, db.DB_FILES)

    def restore():
        db.DATA_DIR, db.REAL_DB, db.DEMO_DB, db.MODE_FILE, db.DB_FILES = originals

    test.addCleanup(restore)
    db.DATA_DIR, db.REAL_DB, db.DEMO_DB = data, data / "salon.db", data / "demo.db"
    db.MODE_FILE = data / "mode.txt"
    db.DB_FILES = {"real": db.REAL_DB, "demo": db.DEMO_DB}


class PhoneTests(unittest.TestCase):
    def test_tidies_common_formats(self):
        self.assertEqual(normalise_phone("+91 98450-12345"), "9845012345")
        self.assertEqual(normalise_phone("098450 12345"), "9845012345")
        self.assertEqual(normalise_phone("98450 12345"), "9845012345")

    def test_rejects_wrong_length(self):
        self.assertIsNone(normalise_phone("12345"))
        self.assertIsNone(normalise_phone(""))
        self.assertIsNone(normalise_phone(None))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings()
        self.good = {
            "phone": "9845012345", "name": "  Test   Person ",
            "service": self.settings["services"][0]["name"], "price": "300",
            "visit_date": TODAY.isoformat(), "staff": self.settings["salon"]["staff"][0],
        }

    def check(self, mode="real", existing=False, **changes):
        return validate_visit({**self.good, **changes}, self.settings, mode, TODAY, existing)

    def test_good_visit_passes_and_is_tidied(self):
        clean, errors = self.check()
        self.assertEqual(errors, {})
        self.assertEqual(clean["name"], "Test Person")
        self.assertEqual(clean["price"], 300)

    def test_real_mode_needs_real_indian_mobile(self):
        _, errors = self.check(phone="5123456789")
        self.assertIn("phone", errors)

    def test_demo_mode_needs_fake_number_starting_with_5(self):
        _, errors = self.check(mode="demo")
        self.assertIn("phone", errors)
        _, errors = self.check(mode="demo", phone="5123456789")
        self.assertNotIn("phone", errors)

    def test_future_date_rejected(self):
        _, errors = self.check(visit_date=(TODAY + timedelta(days=1)).isoformat())
        self.assertIn("visit_date", errors)

    def test_unknown_service_staff_and_bad_price_rejected(self):
        _, errors = self.check(service="Tattoo", staff="Nobody", price="abc")
        self.assertEqual(set(errors), {"service", "staff", "price"})

    def test_name_needed_only_for_new_customers(self):
        _, errors = self.check(name="")
        self.assertIn("name", errors)
        _, errors = self.check(name="", existing=True)
        self.assertNotIn("name", errors)


class StatusTests(unittest.TestCase):
    def test_groups(self):
        self.assertEqual(customer_status(1, 10, None, RULES), "one-time")
        self.assertEqual(customer_status(2, 10, 30, RULES), "occasional")
        self.assertEqual(customer_status(5, 40, 30, RULES), "regular")   # 40 <= 1.5 x 30
        self.assertEqual(customer_status(5, 46, 30, RULES), "overdue")   # 46 >  1.5 x 30

    def test_same_day_services_count_as_one_visit(self):
        d = TODAY.isoformat()
        rows = [
            {"id": 1, "name": "A", "phone": "5000000001", "visit_date": d, "service": "Haircut", "price": 300},
            {"id": 1, "name": "A", "phone": "5000000001", "visit_date": d, "service": "Head Massage", "price": 350},
        ]
        [c] = build_customer_list(rows, TODAY, RULES)
        self.assertEqual(c["visits"], 1)
        self.assertEqual(c["avg_spend"], 650)
        self.assertEqual(c["status"], "one-time")


class ApiTests(unittest.TestCase):
    def setUp(self):
        use_temporary_databases(self)
        self.client = app.test_client()
        settings = load_settings()
        self.visit = {
            "phone": "9845012345", "name": "Test Person",
            "service": settings["services"][0]["name"], "price": 300,
            "visit_date": TODAY.isoformat(), "staff": settings["salon"]["staff"][0],
        }

    def test_save_new_then_returning_customer(self):
        r = self.client.post("/api/visits", json=self.visit)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.get_json()["new_customer"])

        # Same phone, different name: it's the same customer, and the name is NOT changed.
        r = self.client.post("/api/visits", json={**self.visit, "name": "Someone Else"})
        self.assertFalse(r.get_json()["new_customer"])
        self.assertEqual(r.get_json()["name"], "Test Person")

        [c] = self.client.get("/api/customers").get_json()["customers"]
        self.assertEqual(c["visits"], 1)   # both on the same day = one visit

    def test_lookup(self):
        self.assertFalse(self.client.get("/api/customers/lookup?phone=9845012345").get_json()["found"])
        self.client.post("/api/visits", json=self.visit)
        r = self.client.get("/api/customers/lookup?phone=%2B91 98450 12345").get_json()
        self.assertTrue(r["found"])
        self.assertEqual(r["name"], "Test Person")

    def test_bad_visit_gets_field_errors_and_saves_nothing(self):
        r = self.client.post("/api/visits", json={**self.visit, "price": -5})
        self.assertEqual(r.status_code, 400)
        self.assertIn("price", r.get_json()["errors"])
        self.assertEqual(self.client.get("/api/customers").get_json()["customers"], [])

    def test_real_and_demo_stay_separate(self):
        self.client.post("/api/visits", json=self.visit)                 # real
        self.client.post("/api/mode", json={"mode": "demo"})
        self.assertEqual(self.client.get("/api/customers").get_json()["customers"], [])
        self.client.post("/api/mode", json={"mode": "real"})
        self.assertEqual(len(self.client.get("/api/customers").get_json()["customers"]), 1)


if __name__ == "__main__":
    unittest.main()
