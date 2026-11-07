# CLAUDE.md — rules for working on Salon Customer Insights

These rules apply to anyone (human or AI) working in this project.

## Hard rules (never break these)

1. **Never print, cat or display `.env` or any API key — not even partly.**
   Refer to it by name only (for example "the `ANTHROPIC_API_KEY` in `.env`").
   To check that a key exists, test it without showing it
   (for example `test -n "$ANTHROPIC_API_KEY" && echo set`).
2. **Never send customer names or phone numbers to the AI API.**
   Only aggregated numbers (counts, averages, days since last visit, service names,
   weekdays) may leave the laptop. Names are merged into AI-written message
   templates *locally*, after the AI reply comes back.
   Everything sent to the AI goes through `insights.build_ai_summary()` and
   `insights.check_no_personal_data()`. Never bypass that check, and never send
   staff names either.
3. **Never print personal details:** no real names, emails or machine hostnames
   in code, logs, commits, docs or terminal output. Demo data uses invented
   names and obviously fake phone numbers.

## Project conventions

- **Stack:** Python + Flask (web server), SQLite (database file), plain
  HTML/CSS/JavaScript (screens), Chart.js (charts). See `PLAN.md` for why.
- **One start command:** `python3 start.py` (Windows: `py start.py`).
- **All salon-specific values live in `settings.toml`** (salon name, services,
  prices, staff, AI model). Never hard-code them in Python or JavaScript.
- **The AI model name lives in `settings.toml`** (`[ai] model`), currently
  `claude-sonnet-5-5`.
- **Demo data and real data are separate database files:**
  `data/demo.db` and `data/salon.db`. Demo scripts must never touch `salon.db`.
- **Demo phone numbers start with `5`** (not a valid Indian mobile prefix) so a
  WhatsApp link can never reach a real person.
- The server listens on `127.0.0.1` only, so other devices on the Wi-Fi can't reach it.
- The screens talk to the server only through `/api/...` JSON endpoints. This
  keeps the door open for an Android app or online version later.
- Keep code beginner-friendly: short functions, plain names, comments that
  explain *why*.
- Small, well-named commits. Do not change the git author name or email.
- Tests never call the real AI: replace `insights.ask_claude` with a fake (see `tests/test_insights.py`).
- Work in stages (see `PLAN.md`) and stop for review after each stage.
