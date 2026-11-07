"""
Reads settings.toml (salon name, services, prices, staff, AI model).

It lives in its own small file so that both the web server (app.py) and the
demo data script can use it.
"""

import tomllib
from pathlib import Path

# The project folder. Every other path is built from this one.
BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "settings.toml"


def load_settings() -> dict:
    """Read settings.toml fresh each time, so edits show up after a restart."""
    with open(SETTINGS_FILE, "rb") as f:
        return tomllib.load(f)
