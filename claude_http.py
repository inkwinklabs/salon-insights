"""
A tiny stand-in for the official Claude library, used only on Android.

Why it exists: the official `anthropic` library depends on parts written in
another language (Rust) that have no Android build yet, so it can't be
installed inside the phone app. The Claude API itself is just a web address
you send JSON to, so this file does that with Python's built-in tools.

It copies only the small piece of the official library that insights.py uses
(same names, same errors), so insights.py reads the same on laptop and phone:

    client = Anthropic(timeout=180.0)
    response = client.beta.messages.create(model=..., messages=[...], ...)

The API key is read from the ANTHROPIC_API_KEY setting and is only ever put
into the request header. It is never printed or saved by this file.
"""

import json
import os
import urllib.error
import urllib.request
from types import SimpleNamespace

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


# ---- the same error names the official library uses

class APIConnectionError(Exception):
    """Couldn't reach the service at all (no internet, timeout)."""


class APIStatusError(Exception):
    """The service answered, but with an error code."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class BadRequestError(APIStatusError): pass          # 400
class AuthenticationError(APIStatusError): pass      # 401
class PermissionDeniedError(APIStatusError): pass    # 403
class NotFoundError(APIStatusError): pass            # 404
class RateLimitError(APIStatusError): pass           # 429

ERRORS_BY_CODE = {400: BadRequestError, 401: AuthenticationError, 403: PermissionDeniedError,
                  404: NotFoundError, 429: RateLimitError}


def as_object(value):
    """Turn the reply's JSON into objects, so response.usage.input_tokens works."""
    if isinstance(value, dict):
        return SimpleNamespace(**{k: as_object(v) for k, v in value.items()})
    if isinstance(value, list):
        return [as_object(v) for v in value]
    return value


class Messages:
    def __init__(self, timeout: float):
        self.timeout = timeout

    def create(self, betas=None, **body):
        headers = {
            "content-type": "application/json",
            "anthropic-version": API_VERSION,
            "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
        }
        if betas:
            # In a plain web request, beta features are named in a header.
            headers["anthropic-beta"] = ",".join(betas)
        request = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"),
                                         headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as reply:
                data = json.loads(reply.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                message = json.loads(e.read().decode("utf-8"))["error"]["message"]
            except Exception:
                message = f"HTTP {e.code}"
            raise ERRORS_BY_CODE.get(e.code, APIStatusError)(e.code, message) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise APIConnectionError(str(e)) from None
        except json.JSONDecodeError:
            raise APIStatusError(502, "The reply was not valid JSON") from None
        return as_object(data)


class Anthropic:
    """client.beta.messages.create(...) — the one call insights.py makes."""

    def __init__(self, timeout: float = 600.0):
        self.beta = SimpleNamespace(messages=Messages(timeout))
