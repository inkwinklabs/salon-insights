# Salon Customer Insights

A small app that runs on the salon's own laptop. It shows who your regulars are,
who has stopped coming, and which days and services make money, and it suggests
what to do next with help from AI.

## Start it

You need Python 3.11 or newer.

**Windows:** double-click **`start.bat`**.

**Mac / Linux** (or Windows from a terminal):

```bash
python3 start.py        # Windows terminal: py start.py
```

On the first run it creates a private library folder (`.venv`) and installs what it
needs. This takes a minute and needs internet. After that, startup is instant and
works offline. Your browser opens at http://127.0.0.1:8000.

Press `Ctrl+C` in the terminal to stop it.

Add `--no-browser` if you don't want a browser tab to open automatically.

## Real data and demo data

The **Real / Demo** switch at the top chooses which data the app shows. They are
kept in two separate files, so one can never mix with the other:

- `data/salon.db`: your real customers (the app starts here)
- `data/demo.db`: 80 made-up customers for trying things out. A yellow
  **DEMO MODE** banner shows while it's in use.

In demo mode, use the **Load demo data** and **Clear demo data** buttons, or from a terminal:

```bash
python3 scripts/make_demo_data.py          # load (or reload) demo data
python3 scripts/make_demo_data.py --clear  # empty demo data
```

Demo phone numbers start with 5, which no Indian mobile number does, so a
WhatsApp link can never message a real person.

## Change salon name, services, prices or staff

Edit `settings.toml`, then restart the app.

## More

- `PLAN.md`: why we picked these tools and how the pieces fit
- `CLAUDE.md`: project rules (privacy and safety)
