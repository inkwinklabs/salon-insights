"""
Tests for the parts that only matter inside the Android app:
  - the pass-code check (other apps on the phone must not reach the server)
  - saving the AI key (phone only; the key must never be sent back)
  - claude_http.py, the stand-in for the official Claude library

Run them with:   .venv/bin/python -m unittest

No test here talks to the real AI or to a real phone: both are replaced by fakes.
"""

import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_file  # noqa: E402
import claude_http  # noqa: E402

TOKEN = "this-run's-random-pass-code"


def on_a_phone():
    """Pretend, for one test, that the server is running inside the Android app."""
    return mock.patch.multiple(app_file, ON_PHONE=True), \
        mock.patch.dict(os.environ, {"SALON_APP_TOKEN": TOKEN})


class PassCodeTests(unittest.TestCase):
    def setUp(self):
        for patch in on_a_phone():
            patch.start()
            self.addCleanup(patch.stop)
        self.client = app_file.app.test_client()

    def test_no_pass_code_no_answer(self):
        for address in ["/", "/api/customers", "/api/settings", "/static/app.js"]:
            self.assertEqual(self.client.get(address).status_code, 403, address)

    def test_wrong_pass_code_is_refused(self):
        self.client.set_cookie("salon_token", "a-guess")
        self.assertEqual(self.client.get("/api/health").status_code, 403)

    def test_right_pass_code_is_let_in(self):
        self.client.set_cookie("salon_token", TOKEN)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_refuses_everything_if_no_pass_code_was_set(self):
        with mock.patch.dict(os.environ, {"SALON_APP_TOKEN": ""}):
            self.client.set_cookie("salon_token", "")
            self.assertEqual(self.client.get("/api/health").status_code, 403)

    def test_laptop_needs_no_pass_code(self):
        with mock.patch.object(app_file, "ON_PHONE", False):
            self.assertEqual(app_file.app.test_client().get("/api/health").status_code, 200)


class AIKeyTests(unittest.TestCase):
    def setUp(self):
        for patch in on_a_phone():
            patch.start()
            self.addCleanup(patch.stop)
        # A fake android_main, because the real one needs Android to lock the key away.
        self.fake_android = mock.Mock()
        patch = mock.patch.dict(sys.modules, {"android_main": self.fake_android})
        patch.start()
        self.addCleanup(patch.stop)
        self.client = app_file.app.test_client()
        self.client.set_cookie("salon_token", TOKEN)

    def test_saves_a_key_and_never_sends_it_back(self):
        key = "sk-ant-test-placeholder"
        reply = self.client.post("/api/ai-key", json={"key": f"  {key} "})
        self.assertEqual(reply.status_code, 200)
        self.fake_android.save_api_key.assert_called_once_with(key)
        self.assertNotIn(key, reply.get_data(as_text=True))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": key}):
            settings = self.client.get("/api/settings")
        self.assertTrue(settings.get_json()["ai_key_saved"])
        self.assertNotIn(key, settings.get_data(as_text=True))

    def test_rejects_things_that_are_not_a_key(self):
        for bad in ["hello", "sk-ant-has a space", "sk-ant-" + "x" * 400]:
            self.assertEqual(self.client.post("/api/ai-key", json={"key": bad}).status_code, 400, bad)
        self.fake_android.save_api_key.assert_not_called()

    def test_empty_key_removes_it(self):
        reply = self.client.post("/api/ai-key", json={"key": ""})
        self.assertFalse(reply.get_json()["ai_key_saved"])
        self.fake_android.save_api_key.assert_called_once_with("")

    def test_not_available_on_a_laptop(self):
        with mock.patch.object(app_file, "ON_PHONE", False):
            reply = app_file.app.test_client().post("/api/ai-key", json={"key": "sk-ant-test-placeholder"})
        self.assertEqual(reply.status_code, 404)


class FakeReply(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class ClaudeHttpTests(unittest.TestCase):
    """The stand-in must behave like the small part of the official library we use."""

    def ask(self, **extra):
        return claude_http.Anthropic(timeout=5).beta.messages.create(
            model="claude-sonnet-5-5", max_tokens=100, messages=[{"role": "user", "content": "hi"}], **extra)

    def test_sends_the_request_and_reads_the_reply(self):
        answer = {"stop_reason": "end_turn", "model": "claude-sonnet-5-5",
                  "content": [{"type": "text", "text": "{}"}],
                  "usage": {"input_tokens": 10, "output_tokens": 2}}
        with mock.patch("urllib.request.urlopen", return_value=FakeReply(json.dumps(answer).encode())) as web, \
             mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-placeholder"}):
            reply = self.ask(betas=["some-beta"])
        request = web.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.get_header("X-api-key"), "test-placeholder")
        self.assertEqual(request.get_header("Anthropic-beta"), "some-beta")
        self.assertNotIn("betas", json.loads(request.data))          # betas go in the header, not the body
        self.assertEqual(reply.content[0].text, "{}")
        self.assertEqual(reply.usage.input_tokens, 10)

    def test_error_codes_become_the_same_errors_as_the_official_library(self):
        cases = {401: claude_http.AuthenticationError, 404: claude_http.NotFoundError,
                 429: claude_http.RateLimitError, 500: claude_http.APIStatusError}
        for code, error in cases.items():
            body = io.BytesIO(json.dumps({"error": {"message": "nope"}}).encode())
            failure = urllib.error.HTTPError("https://api.anthropic.com/v1/messages", code, "x", {}, body)
            with mock.patch("urllib.request.urlopen", side_effect=failure):
                with self.assertRaises(error) as caught:
                    self.ask()
            self.assertEqual(caught.exception.status_code, code)

    def test_no_internet_is_a_connection_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaises(claude_http.APIConnectionError):
                self.ask()


if __name__ == "__main__":
    unittest.main()
