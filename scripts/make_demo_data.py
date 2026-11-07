"""
Makes about 80 made-up customers and 6 months of visits in data/demo.db.

    python scripts/make_demo_data.py          load (or reload) demo data
    python scripts/make_demo_data.py --clear  empty the demo data

The app's "Load demo data" button runs the same code.

SAFETY
  - It only ever writes to data/demo.db, never the real data/salon.db.
  - Phone numbers start with 5. Indian mobile numbers start with 6, 7, 8 or 9,
    so a WhatsApp link to these numbers can never reach a real person.
  - Names are random first-name + surname combinations, not real people.

PATTERNS PLANTED FOR THE AI TO FIND
  - Tuesday is the quiet day (about a third of a normal day's visits).
  - Saturday and Sunday are the busiest.
  - 12 regular customers stopped coming 2-3 months ago (overdue).
  - A small group of "premium" customers book the costliest services, so
    those services earn the most per visit.
  - 15 customers came only once.
  - Regulars come mainly for haircuts and beard trims; head massages are add-ons.
  - New customers arrive every month, but revenue dips after mid-year when the
    overdue regulars stop coming (a "lost regulars cost you money" story).

A fixed "random seed" means the same data comes out every time it's run on the
same day, which makes it easy to check. Dates count back from today, so the
overdue customers are always overdue, whenever you load it.
"""

import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Let this script find db.py and settings.py in the folder above.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from settings import load_settings  # noqa: E402

DAYS_OF_HISTORY = 182  # about 6 months

# How likely a visit is on each weekday (Monday=0 ... Sunday=6).
# Tuesday's 0.3 is the planted "quiet day".
WEEKDAY_WEIGHT = [1.0, 0.3, 0.9, 1.0, 1.2, 1.8, 1.6]

# What regulars mainly come for, and how often each is picked (bigger = more).
MAIN_SERVICE_WEIGHTS = {"Haircut": 4, "Haircut + Beard": 3, "Beard Trim": 2, "Kids Haircut": 1}

# How many customers in each group.
GROUP_SIZES = {
    "active_regular": 35,   # come every few weeks and still coming
    "overdue_regular": 12,  # were regular, then stopped 2-3 months ago
    "premium": 10,          # book the expensive services
    "occasional": 8,        # came twice
    "one_time": 15,         # came once
}

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karthik", "Sai", "Vikram", "Rahul", "Nikhil",
    "Siddharth", "Pranav", "Harsh", "Manoj", "Suresh", "Ganesh", "Imran", "Farhan", "Abhishek", "Deepak",
    "Varun", "Kiran", "Naveen", "Prakash", "Rajesh", "Tarun", "Yash", "Gaurav", "Sandeep", "Anil",
    "Ananya", "Diya", "Priya", "Kavya", "Sneha", "Pooja", "Meera", "Lakshmi", "Divya", "Neha",
    "Shreya", "Ritu", "Swati", "Nandini", "Aisha", "Fatima", "Bhavana", "Keerthi", "Harini", "Sunita",
]
SURNAMES = [
    "Sharma", "Verma", "Iyer", "Reddy", "Nair", "Rao", "Gupta", "Patel", "Menon", "Kulkarni",
    "Joshi", "Desai", "Pillai", "Shetty", "Hegde", "Khan", "Sheikh", "Mehta", "Bhat", "Naidu",
    "Chopra", "Malhotra", "Banerjee", "Das", "Mishra", "Pandey", "Gowda", "Krishnan", "Agarwal", "Singh",
]


class DemoDataMaker:
    def __init__(self, today: date | None = None, seed: int = 42):
        self.rng = random.Random(seed)
        self.today = today or date.today()
        self.start = self.today - timedelta(days=DAYS_OF_HISTORY)

        settings = load_settings()
        self.staff = settings["salon"]["staff"]
        services = sorted(settings["services"], key=lambda s: s["price"])
        self.service_by_name = {s["name"]: s for s in services}
        # The 3 priciest services are "premium"; the rest are everyday services.
        # Picking them by price (not by name) keeps this working if settings.toml changes.
        self.premium_services = services[-3:]
        self.everyday_services = services[:-3]

        self.used_names: set[str] = set()
        self.used_phones: set[str] = set()
        self.customers: list[dict] = []  # each: name, phone, group, visits[]

    # ------------------------------------------------------------ small helpers

    def new_name(self) -> str:
        while True:
            name = f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(SURNAMES)}"
            if name not in self.used_names:
                self.used_names.add(name)
                return name

    def new_fake_phone(self) -> str:
        """10 digits starting with 5: never a valid Indian mobile number."""
        while True:
            phone = "5" + "".join(str(self.rng.randint(0, 9)) for _ in range(9))
            if phone not in self.used_phones:
                self.used_phones.add(phone)
                return phone

    def day_near(self, target: date, spread: int = 3) -> date:
        """Pick a day close to `target`, preferring busy weekdays (so Tuesday stays quiet)."""
        options = [target + timedelta(days=d) for d in range(-spread, spread + 1)]
        options = [d for d in options if self.start <= d <= self.today] or [target]
        weights = [WEEKDAY_WEIGHT[d.weekday()] for d in options]
        return self.rng.choices(options, weights=weights)[0]

    def random_day(self) -> date:
        """Any day in the 6 months."""
        return self.day_near(self.start + timedelta(days=self.rng.randint(0, DAYS_OF_HISTORY)))

    def growing_day(self, i: int, n: int) -> date:
        """Day for new customer number i of n, with more of them in recent months.

        We split the 6 months into n slices so every month gets some newcomers
        (pure chance could leave a month empty), and the square root packs
        more slices into recent months, so the business grows.
        """
        share = (i + self.rng.random()) / n          # 0..1, evenly spread
        offset = int(DAYS_OF_HISTORY * share ** 0.5)  # leans towards today
        return self.day_near(self.start + timedelta(days=offset))

    def price_for(self, service: dict) -> int:
        """Usually the list price; sometimes a small discount or extra (±5%, rounded to ₹10)."""
        price = service["price"]
        if self.rng.random() < 0.2:
            price = round(price * self.rng.uniform(0.95, 1.05) / 10) * 10
        return price

    def visit(self, day: date, service: dict, favourite_staff: str) -> dict:
        staff = favourite_staff if self.rng.random() < 0.8 else self.rng.choice(self.staff)
        return {"date": day, "service": service["name"], "price": self.price_for(service), "staff": staff}

    def repeating_visits(self, service: dict, first: date, last_allowed: date, gap: int,
                         favourite_staff: str, extras: list[dict]) -> list[dict]:
        """Visits every `gap` days (give or take 20%) from `first` until `last_allowed`."""
        visits = []
        day = self.day_near(first)
        while day <= last_allowed:
            # Now and then the customer picks something else (e.g. a head massage).
            chosen = self.rng.choice(extras) if extras and self.rng.random() < 0.15 else service
            visits.append(self.visit(day, chosen, favourite_staff))
            next_target = day + timedelta(days=round(gap * self.rng.uniform(0.8, 1.2)))
            day = self.day_near(next_target)
        return visits

    def add_customer(self, group: str, visits: list[dict]) -> None:
        if visits:
            self.customers.append({
                "name": self.new_name(), "phone": self.new_fake_phone(),
                "group": group, "visits": visits,
            })

    # ------------------------------------------------------------ the groups

    def main_service(self, regular_services: list[dict]) -> dict:
        """What a regular mainly comes for: mostly haircuts, sometimes beard trims.

        Head massage etc. stay as occasional add-ons. If settings.toml no longer
        has these names, fall back to any cheap, frequent service.
        """
        options = [(self.service_by_name[n], w) for n, w in MAIN_SERVICE_WEIGHTS.items()
                   if n in self.service_by_name]
        if not options:
            return self.rng.choice(regular_services)
        services, weights = zip(*options)
        return self.rng.choices(services, weights=weights)[0]

    def make_all(self) -> None:
        everyday = self.everyday_services
        # Cheap, frequent services: the fallback if the usual names are missing.
        regular_services = [s for s in everyday if s["typical_gap_days"] <= 35]

        n = GROUP_SIZES["active_regular"]
        for i in range(n):
            service = self.main_service(regular_services)
            gap = round(service["typical_gap_days"] * self.rng.uniform(0.8, 1.1))
            # They join steadily over the first 4 months, so the regular base
            # keeps growing (this is the "gentle growth" pattern).
            first = self.start + timedelta(days=int(120 * (i + self.rng.random()) / n))
            staff = self.rng.choice(self.staff)
            self.add_customer("active_regular", self.repeating_visits(
                service, first, self.today, gap, staff, everyday))

        for _ in range(GROUP_SIZES["overdue_regular"]):
            # Haircut regulars, every 3-4 weeks...
            haircuts = [self.service_by_name[n] for n in ("Haircut", "Haircut + Beard")
                        if n in self.service_by_name]
            service = self.rng.choice(haircuts or regular_services)
            gap = self.rng.randint(21, 30)
            first = self.start + timedelta(days=self.rng.randint(0, 20))
            # ...who suddenly stopped 60-100 days ago.
            stopped = self.today - timedelta(days=self.rng.randint(60, 100))
            staff = self.rng.choice(self.staff)
            visits = self.repeating_visits(service, first, stopped, gap, staff, [])
            # Make sure each one really looks like a regular (at least 3 visits).
            while len(visits) < 3:
                visits.insert(0, self.visit(visits[0]["date"] - timedelta(days=gap), service, staff))
            self.add_customer("overdue_regular", visits)

        for _ in range(GROUP_SIZES["premium"]):
            service = self.rng.choice(self.premium_services)
            gap = self.rng.randint(28, 40)
            first = self.start + timedelta(days=self.rng.randint(0, 30))
            staff = self.rng.choice(self.staff)
            # Premium customers sometimes add another premium service.
            self.add_customer("premium", self.repeating_visits(
                service, first, self.today, gap, staff, self.premium_services))

        for _ in range(GROUP_SIZES["occasional"]):
            d1 = self.random_day()
            d2 = self.random_day()
            staff = self.rng.choice(self.staff)
            visits = [self.visit(d, self.rng.choice(everyday), staff) for d in sorted({d1, d2})]
            self.add_customer("occasional", visits)

        n = GROUP_SIZES["one_time"]
        for i in range(n):
            # New walk-ins: spread over every month, more of them recently.
            day = self.growing_day(i, n)
            service = self.rng.choice(everyday + self.premium_services[:1])
            self.add_customer("one_time", [self.visit(day, service, self.rng.choice(self.staff))])

    # ------------------------------------------------------------ saving

    def save(self) -> None:
        """Replace everything in demo.db with the new customers and visits."""
        db.clear_demo()
        with db.open_db(db.DEMO_DB) as conn:
            for c in self.customers:
                c["visits"].sort(key=lambda v: v["date"])
                cur = conn.execute(
                    "INSERT INTO customers (name, phone, created_at) VALUES (?, ?, ?)",
                    (c["name"], c["phone"], c["visits"][0]["date"].isoformat()),
                )
                conn.executemany(
                    "INSERT INTO visits (customer_id, service, price, visit_date, staff) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [(cur.lastrowid, v["service"], v["price"], v["date"].isoformat(), v["staff"])
                     for v in c["visits"]],
                )


def load_demo_data(today: date | None = None) -> dict:
    """Build and save the demo data. Returns counts per group (no names)."""
    maker = DemoDataMaker(today=today)
    maker.make_all()
    maker.save()
    groups = {g: 0 for g in GROUP_SIZES}
    for c in maker.customers:
        groups[c["group"]] += 1
    return {
        "customers": len(maker.customers),
        "visits": sum(len(c["visits"]) for c in maker.customers),
        "groups": groups,
    }


if __name__ == "__main__":
    if "--clear" in sys.argv:
        db.clear_demo()
        print("Demo data cleared (data/demo.db is now empty). Real data was not touched.")
    else:
        result = load_demo_data()
        print(f"Demo data loaded into data/demo.db: "
              f"{result['customers']} customers, {result['visits']} visits.")
        for group, count in result["groups"].items():
            print(f"  {group:<16} {count}")
        print("Real data (data/salon.db) was not touched.")
