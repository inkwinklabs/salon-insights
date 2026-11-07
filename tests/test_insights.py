"""
Tests for stage 5: the AI summary's privacy, the reminder template, and the
insights and reminders routes.

None of these tests call the real AI. ask_claude() is replaced with a fake,
so the tests are free, fast and work offline.
"""

import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
import insights  # noqa: E402
from app import app  # noqa: E402
from settings import load_settings  # noqa: E402
from tests.test_visits_and_customers import use_temporary_databases  # noqa: E402

TODAY = date.today()
FAKE_REPLY = {
    "headline": "12 regulars are overdue.",
    "insights": [{"title": "Win back regulars", "finding": "3 are overdue", "action": "Message them",
                  "topic": "retention", "priority": "high"}],
    "reminder_template": "Hi {name}, we miss you at {salon}! Time for your {service}?",
    "model": "claude-sonnet-5-5",
    "usage": {"input_tokens": 1000, "output_tokens": 300},
}


def add_visits(phone, name, days_ago_list, service="Haircut", price=300):
    for d in days_ago_list:
        db.add_visit({"phone": phone, "name": name, "service": service, "price": price,
                      "visit_date": (TODAY - timedelta(days=d)).isoformat(), "staff": "Ravi"})


class InsightsTestCase(unittest.TestCase):
    def setUp(self):
        use_temporary_databases(self)
        db.set_mode("demo")
        self.settings = load_settings()
        # An overdue regular, an on-time regular, and a one-time customer.
        add_visits("5111111111", "Overdue Person", [150, 125, 100, 75])
        add_visits("5222222222", "Regular Person", [60, 30, 5])
        add_visits("5333333333", "Once Person", [10], service="Facial", price=1200)


class SummaryPrivacyTests(InsightsTestCase):
    def test_summary_has_numbers_but_no_names_phones_or_staff(self):
        summary, customers = insights.build_ai_summary(TODAY, self.settings)
        text = insights.summary_as_text(summary)
        for secret in ["Overdue Person", "Regular Person", "Once Person",
                       "5111111111", "5222222222", "5333333333", "Ravi"]:
            self.assertNotIn(secret, text)
        insights.check_no_personal_data(text, customers)  # must not raise

        self.assertEqual(summary["customer_groups"], {"overdue": 1, "regular": 1, "one-time": 1})
        [row] = summary["overdue_regulars"]
        self.assertEqual(row["days_since_last_visit"], 75)
        self.assertEqual(row["usual_gap_days"], 25)
        self.assertNotIn("id", row)

    def test_privacy_check_stops_names_phones_and_10_digit_numbers(self):
        _, customers = insights.build_ai_summary(TODAY, self.settings)
        for leaked in ['{"x": "overdue person"}', '{"x": "5111111111"}', '{"x": "call 9845012345"}']:
            with self.assertRaises(insights.PrivacyError):
                insights.check_no_personal_data(leaked, customers)

    def test_nothing_is_sent_if_the_check_fails(self):
        with mock.patch.object(insights, "summary_as_text", return_value="Overdue Person"), \
             mock.patch.object(insights, "ask_claude") as fake:
            with self.assertRaises(insights.PrivacyError):
                insights.generate_insights(self.settings, TODAY)
            fake.assert_not_called()


class TemplateTests(unittest.TestCase):
    DEFAULT = "Hi {name}!"

    def test_good_template_is_kept(self):
        t, note = insights.clean_template("Hello {name}, time for your {service} at {salon}?", self.DEFAULT)
        self.assertIn("{service}", t)
        self.assertIsNone(note)

    def test_bad_templates_fall_back_to_default(self):
        for bad in ["", "Hello there!", "Hi {name}, {offer} today", "Hi {name}, book at https://x.co",
                    "Hi {name} " + "x" * 700]:
            t, note = insights.clean_template(bad, self.DEFAULT)
            self.assertEqual(t, self.DEFAULT, bad[:30])
            self.assertIsNotNone(note)


class InsightsApiTests(InsightsTestCase):
    def setUp(self):
        super().setUp()
        self.client = app.test_client()

    def test_generate_saves_and_reminders_use_ai_template(self):
        self.assertIsNone(self.client.get("/api/insights").get_json()["result"])
        with mock.patch.object(insights, "ask_claude", return_value=dict(FAKE_REPLY)) as fake:
            r = self.client.post("/api/insights", json={})
        self.assertEqual(r.status_code, 200)
        sent_text = fake.call_args.args[0]
        self.assertNotIn("Overdue Person", sent_text)
        self.assertEqual(r.get_json()["result"]["headline"], FAKE_REPLY["headline"])
        # Saved, so it comes back without another AI call.
        self.assertEqual(self.client.get("/api/insights").get_json()["result"]["headline"], FAKE_REPLY["headline"])

        rem = self.client.get("/api/reminders").get_json()
        self.assertEqual(rem["template_source"], "ai")
        self.assertEqual(rem["template"], FAKE_REPLY["reminder_template"])
        [c] = rem["customers"]
        self.assertEqual((c["name"], c["phone"]), ("Overdue Person", "5111111111"))

    def test_missing_key_gives_a_clear_message(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            r = self.client.post("/api/insights", json={})
        self.assertEqual(r.status_code, 503)
        self.assertIn(".env", r.get_json()["error"])

    def test_preview_shows_summary_and_passes_check(self):
        p = self.client.get("/api/insights/preview").get_json()
        self.assertTrue(p["passed_privacy_check"])
        self.assertNotIn("Overdue Person", p["summary"] + p["instructions"])
        self.assertEqual(p["model"], self.settings["ai"]["model"])

    def test_reminder_opened_is_remembered(self):
        [c] = self.client.get("/api/reminders").get_json()["customers"]
        self.assertIsNone(c["last_reminder"])
        self.assertEqual(self.client.post(f"/api/reminders/{c['id']}/opened", json={}).status_code, 200)
        [c] = self.client.get("/api/reminders").get_json()["customers"]
        self.assertTrue(c["last_reminder"].startswith(TODAY.isoformat()))
        self.assertEqual(self.client.post("/api/reminders/9999/opened", json={}).status_code, 404)

    def test_default_template_before_any_ai_call(self):
        rem = self.client.get("/api/reminders").get_json()
        self.assertEqual(rem["template_source"], "default")
        self.assertEqual(rem["template"], self.settings["reminders"]["default_template"])


if __name__ == "__main__":
    unittest.main()


class GarbledReplyTests(unittest.TestCase):
    """A reply that isn't valid JSON gives a friendly message, not a crash."""

    def test_garbled_reply(self):
        fake_response = mock.Mock(stop_reason="end_turn", model="claude-sonnet-5-5",
                                  content=[mock.Mock(type="text", text="this is {not json")])
        fake_client = mock.Mock()
        fake_client.beta.messages.create.return_value = fake_response
        with mock.patch.object(insights.anthropic, "Anthropic", return_value=fake_client), \
             mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-placeholder"}):
            with self.assertRaises(insights.InsightsError) as caught:
                insights.ask_claude("{}", load_settings())
        self.assertIn("couldn't be read", str(caught.exception))

    def test_refusal_and_cut_off_replies(self):
        for reason, words in [("refusal", "declined"), ("max_tokens", "cut off")]:
            fake_client = mock.Mock()
            fake_client.beta.messages.create.return_value = mock.Mock(stop_reason=reason, content=[])
            with mock.patch.object(insights.anthropic, "Anthropic", return_value=fake_client), \
                 mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-placeholder"}):
                with self.assertRaises(insights.InsightsError) as caught:
                    insights.ask_claude("{}", load_settings())
            self.assertIn(words, str(caught.exception))
