# Plan — Salon Customer Insights

## 1. Choosing the stack

A "stack" is just the set of tools the app is built with. We need:

| Need | Why it matters |
|---|---|
| One simple start command | A salon owner shouldn't need to type ten commands |
| Beginner-friendly | You should be able to read the code and follow it |
| Local database, no cloud account | Free, private, works without internet |
| Online or Android later without a full rewrite | Protects the work if this becomes a product |

### Options compared

| Option | What it is | Good | Not so good |
|---|---|---|---|
| **A. Python + Flask + SQLite + plain HTML/JS** | Small Python web server; screens are ordinary web pages | Python reads almost like English. Flask is about the smallest web server there is. SQLite is built into Python, so there's nothing extra to install. Good at number-crunching for the dashboard. | Two languages (Python on the server, JavaScript in the browser) |
| B. Node.js + Express + SQLite + plain HTML/JS | Same shape as A, but JavaScript everywhere | One language | Node's built-in SQLite is still marked "experimental" on this laptop's Node 22; the alternatives need compiling. Data maths is wordier than in Python. |
| C. Streamlit (Python) | Write Python and it draws the screens for you | Fastest to get charts on screen | You give up control of the look. Very hard to turn into an Android app later. The whole page re-runs on every click, which is confusing to learn from. |
| D. Next.js / React + a database server | What many startups use | Very powerful | Far too many moving parts for a beginner: build tools, components, a separate database server |

### Decision: **Option A, Python + Flask + SQLite + plain HTML/CSS/JavaScript (+ Chart.js for charts)**

Why, in plain words:

- **Easy to read.** Every screen is a normal web page. Every piece of server logic is
  a short Python function. No build step and no framework magic.
- **Nothing to sign up for.** SQLite keeps the whole database in a single file
  (`data/salon.db`). Backing up means copying one file.
- **One command.** `python3 start.py` sets everything up on first run (a private
  library folder called `.venv`), then starts the app and opens the browser.
- **Ready for later without a rewrite.** The screens only talk to the server through
  `/api/...` addresses that send and receive JSON (plain structured text). So:
  - *Online later:* put the same Flask app on a hosting service and swap SQLite for a
    hosted database. The SQL lives in one file (`db.py`), so only that file changes.
  - *Android later:* the screens are already mobile-friendly web pages. They can become
    an installable web app (a PWA) or be wrapped into an Android app with a tool like
    Capacitor, pointing at the online server. The screens and the API stay as they are.

## 2. How the pieces fit

```
 Browser (static/*.html, *.js)          Flask server (app.py)             SQLite file
 ┌───────────────────────┐   /api/...   ┌────────────────────────┐  SQL   ┌──────────────┐
 │ Log visit · Customers │ ───────────▶ │ checks input, does the │ ─────▶ │ data/salon.db│
 │ Dashboard · Insights  │ ◀─────────── │ maths, reads settings  │ ◀───── │ data/demo.db │
 └───────────────────────┘     JSON     └───────────┬────────────┘        └──────────────┘
                                                    │ numbers only, no names/phones
                                                    ▼
                                            Claude API (stage 5)
```

## 3. Privacy design (decided now, built in stage 5)

1. The server builds an **aggregated summary**: counts, averages, days since last
   visit, per service and per weekday. No names, no phone numbers.
2. Only that summary goes to Claude. Claude replies with insights and a **message
   template** containing placeholders like `{name}` and `{service}`.
3. **On the laptop**, the app fills in each overdue customer's name and builds a
   `https://wa.me/<number>?text=...` link. The owner taps it and presses send in WhatsApp.
4. There's a "Show exactly what will be sent" preview, so you can see for yourself
   that no personal data leaves.

## 4. Demo data vs real data

- Two separate database files: `data/demo.db` (sample data) and `data/salon.db` (real).
- A clear **DEMO MODE** banner shows whenever the demo database is active.
- "Load demo data" and "Clear demo data" only ever touch `demo.db`.
- Demo phone numbers start with `5`. Indian mobile numbers start with 6–9, so these
  can never reach a real person.

## 5. Settings

`settings.toml` holds the salon name, services and prices, staff names, the AI model
(`claude-sonnet-5-5`) and reminder rules. TOML is a simple text format that allows
comments, so an owner can edit it in Notepad.

## 6. Stages (we stop for review after each one)

1. **Plan, stack, rules (CLAUDE.md), first commit, a page that runs** ← *this stage*
2. Database design + sample data generator (with deliberate patterns: a quiet weekday,
   overdue regulars, a high-value service, one-time customers) + load/clear demo data
3. Visit form + customer list
4. Dashboard + charts (Chart.js, saved inside the project so it works offline)
5. AI insights + WhatsApp reminders + `READY_TO_SELL.md`
6. Bug fixes, polish, final walkthrough

## 7. Folder layout (end goal)

```
salon-insights/
  start.py          one command to set up and run
  app.py            web server and /api routes
  db.py             all database code (stage 2)
  insights.py       summary builder + Claude call (stage 5)
  settings.toml     salon name, services, prices, staff, AI model
  requirements.txt  Python libraries the app needs
  scripts/          demo data generator (stage 2)
  static/           the screens (HTML, CSS, JS)
  data/             database files (not committed to git)
  CLAUDE.md  PLAN.md  README.md  READY_TO_SELL.md
```
