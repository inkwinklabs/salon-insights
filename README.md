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

## Using the app (a quick tour)

1. **Log visit:** type the customer's phone first. A returning customer's name
   fills in by itself. Pick the service (the price fills in), the date
   (Day · Month · Year, or the **Today** / **Yesterday** buttons) and who did it,
   then **Save visit**.
2. **Customers:** everyone, with visits, last visit, average spend, usual service
   and a status: *Regular*, *Overdue*, *Occasional* or *One-time*. Search, filter,
   sort, and click a customer to see their history. On a phone each customer is a card.
3. **Dashboard:** headline numbers and charts for any period. Click
   **Overdue regulars** to jump to those customers. Every chart has a table view.
4. **AI Insights:** press **Get AI insights** for plain-language suggestions
   (only numbers are sent), then use **Open WhatsApp** to send each overdue
   regular a friendly reminder.

**Theme** (top right) switches between Auto (follows the laptop), Light and Dark.

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

## AI insights and WhatsApp reminders

1. Copy `.env.example` to `.env` and put your Anthropic API key after `ANTHROPIC_API_KEY=`.
   (`.env` is never committed to git.)
2. Open the **AI Insights** tab and press **Get AI insights**. Only numbers are sent,
   with no names or phone numbers. "Show exactly what will be sent" lets you check.
3. Below the insights, each overdue regular has an **Open WhatsApp** button. It opens
   WhatsApp with a friendly message already filled in; you press Send yourself.

Each press of "Get AI insights" is one paid request (about a cent or two).
The model is set in `settings.toml` under `[ai]`.

## Change salon name, services, prices or staff

Edit `settings.toml`, then restart the app. The same file sets when a customer
counts as a **regular** (`min_visits_for_regular`) and when they're **overdue**
(`overdue_factor`: how many times their usual gap between visits).

## Check that everything works

```bash
.venv/bin/python -m unittest        # Windows: .venv\Scripts\python -m unittest
```

The tests use throwaway databases, so they never touch your real or demo data.

## More

- `PLAN.md`: why we picked these tools and how the pieces fit
- `CLAUDE.md`: project rules (privacy and safety)
- `READY_TO_SELL.md`: what's needed before selling this to a real salon
