"""
One command to set up and run the app:

    python3 start.py          (Windows: py start.py)

What it does, step by step:
  1. Makes a private library folder called ".venv" (first run only), so this app's
     libraries never clash with anything else on the laptop.
  2. Installs the libraries listed in requirements.txt (only when that file changes).
  3. Starts the web server (app.py) using that private folder.

It only uses tools built into Python, so it works before anything is installed.
"""

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
# We save a fingerprint of requirements.txt here, so we know when to reinstall.
INSTALLED_STAMP = VENV_DIR / ".installed-requirements"


def venv_python() -> Path:
    """Path to the Python program inside .venv (Windows puts it somewhere else)."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def main() -> None:
    if sys.version_info < (3, 11):
        sys.exit("Please install Python 3.11 or newer (https://www.python.org/downloads/).")

    if not venv_python().exists():
        print("First run: creating a private library folder (.venv) ...")
        venv.create(VENV_DIR, with_pip=True)

    fingerprint = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    already = INSTALLED_STAMP.read_text() if INSTALLED_STAMP.exists() else ""
    if already != fingerprint:
        print("Installing libraries (needs internet, about a minute) ...")
        subprocess.check_call(
            [str(venv_python()), "-m", "pip", "install", "--quiet", "-r", str(REQUIREMENTS)]
        )
        INSTALLED_STAMP.write_text(fingerprint)

    # Run the real app with the private Python, passing on any extra options
    # (for example --no-browser).
    # PYTHONIOENCODING=utf-8 stops Windows terminals crashing on characters like ₹.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.call(
        [str(venv_python()), str(ROOT / "app.py"), *sys.argv[1:]], cwd=ROOT, env=env
    )
    sys.exit(result)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
