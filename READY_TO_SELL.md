# Ready to sell: checklist before a real salon uses this

Today the app is built for one owner on one laptop, with demo data. Before
selling it to a real salon, work through this list. None of it is built yet,
on purpose.

## 1. Who can open it: login or PIN
- [ ] Add a PIN or password screen. Right now anyone using the laptop can see every customer.
- [ ] Lock the app after a few minutes of no use.
- [ ] If staff will use it too: separate staff and owner access (staff log visits; only the owner sees revenue and AI insights).
- [ ] Keep it listening on `127.0.0.1` only (this laptop) unless it's hosted properly (see 3).

## 2. Not losing data: backups and export
- [ ] **Backups.** All real data is one file, `data/salon.db`. Add a "Back up now" button and an automatic daily copy to a USB drive or the owner's own cloud folder. Test restoring from a backup.
- [ ] **CSV export** of customers and visits, so the owner can open them in Excel and is never locked in.
- [ ] **Edit and delete** a mistaken visit (not built yet). Keep a simple log of changes.
- [ ] A safe "Delete a customer" option, needed for the data protection rights below.
- [ ] Clearing **real** data should need typing a confirmation word, and make a backup first (today only demo data can be cleared).

## 3. Hosting: putting it online (only if needed)
- [ ] Decide whether it stays on the laptop (simplest, most private) or goes online (works from a phone or several branches).
- [ ] If online: a proper web server instead of Flask's built-in one, HTTPS, login (see 1), and a hosted database (only `db.py` needs to change).
- [ ] Hosting in India, or check where the data will be stored.
- [ ] An Android app later: the screens already work on a phone and talk to the server only through `/api/...`.

## 4. Customer consent for WhatsApp, and India's data protection law (DPDP Act, 2023)
Not legal advice. Have a lawyer check this before selling.
- [ ] **Ask permission** before messaging: record when and how each customer agreed to WhatsApp reminders (a "consent" yes/no and date on each customer). Only show reminder links for customers who said yes.
- [ ] **Say what you collect and why**: a short notice at the counter or on the bill ("We keep your name, phone and visits to remind you when you're due").
- [ ] **Let customers opt out** ("reply STOP") and record it, and **delete their data** when asked.
- [ ] **Collect only what's needed**: name, phone, visits. Nothing else.
- [ ] Decide who is responsible for the data (the salon, as "Data Fiduciary") and who to contact about it.
- [ ] Report a data breach (for example, a stolen laptop) as the law requires. Encrypting the laptop's disk is a cheap protection.
- [ ] The AI already receives **only numbers**, never names or phones (see `insights.py` and its privacy check). Keep it that way.
- [ ] Reminders are sent one by one by the owner pressing Send. Don't add bulk or automatic messaging without the WhatsApp Business API and its own rules.

## 5. Who pays for the AI
Each "Get AI insights" press is one request to Claude. With the demo data it used about 3,600 input + 1,000 output tokens: **roughly a cent or two each** at current Claude Sonnet 5.5 prices ($2 / $10 per million tokens). Check current prices before quoting.
- [ ] **Option A: you include it.** Use your API key on a small server that the app calls, so the key is never on the salon's laptop. Limit presses (e.g. 30 a month).
- [ ] **Option B: the salon brings its own key.** Simple, but harder for a non-technical owner.
- [ ] Either way: show a monthly count of AI presses, and set a spending limit in the Anthropic Console.
- [ ] The API key must never be inside the app's files that ship to the salon (today it lives in `.env`, which is not committed).

## 6. Pricing ideas
- **One-time setup fee** (e.g. ₹3,000–₹5,000) for install, entering services and staff, and training.
- **Monthly plan** (e.g. ₹299–₹499 a month) that includes backups, updates and a set number of AI insights.
- **Free tier**: visit log, customer list and dashboard free; AI insights and reminders on the paid plan.
- **Multi-branch plan**, priced per branch, once it can go online.
- Try it free for 30 days with 2–3 friendly salons first, and adjust prices to what they'd actually pay.

## 7. Before handing over
- [ ] Put the salon's real name, services, prices and staff in `settings.toml`.
- [ ] Start in **Real** mode with an empty `salon.db`, and show the owner how the Demo switch works.
- [ ] Windows: test `start.bat` on their laptop, and add a desktop shortcut.
- [ ] A one-page "how to use it" sheet, in the owner's language.
