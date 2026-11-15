"""Operating commands: reservations, returns and availability on a persistent store (also served by the web app).

Charges and deposits are a ledger: `rentals` shows what each customer owes or is due back. Taking the
payment and holding the deposit is done through your own payment provider.
"""

import itertools
import json
import os
from datetime import date

from .core import Counter, RentalError

OPS = ("reserve", "return", "rentals", "availability")


def _day(text) -> date:
    try:
        return date.fromisoformat(text) if text else date.today()
    except ValueError:
        raise RentalError(f"{text!r} is not a date like 2026-12-01") from None


def load(path: str) -> Counter:
    c = Counter()
    try:
        with open(path, encoding="utf-8-sig") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return c
    if not isinstance(doc, dict) or not isinstance(doc.get("bookings"), dict):
        raise RentalError(f"{path}: not a robot-rental store")
    c.bookings = doc["bookings"]
    c._ids = itertools.count(int(doc.get("next_id", 1)))
    for b in c.bookings.values():  # a robot is busy on the day of every booking still out
        if b["status"] == "booked":
            for rid in b["robots"]:
                if rid in c.fleet:
                    c.fleet[rid].booked.add(date.fromisoformat(b["date"]))
    return c


def save(c: Counter, path: str):
    next_id = next(c._ids)
    c._ids = itertools.count(next_id)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"bookings": c.bookings, "next_id": next_id}, fh, indent=2)
    os.replace(tmp, path)


def add_ops(sub):
    store = os.environ.get("ROBOT_RENTAL_STORE", "rentals.json")
    p = sub.add_parser("reserve", help="price a job and reserve the robots for that day")
    p.add_argument("customer")
    p.add_argument("job", choices=["move", "deep_clean", "event"])
    p.add_argument("--date", help="YYYY-MM-DD, default today")
    p.add_argument("--km", type=float, default=10, help="delivery distance one way")
    p.add_argument("--rooms", type=int, default=2)
    p.add_argument("--heaviest", type=float, default=50, help="heaviest item in kg (move)")
    p.add_argument("--stairs", action="store_true")
    p.add_argument("--sqft", type=float, default=1200)
    p.add_argument("--detail", action="store_true", help="detailed clean")
    p.add_argument("--guests", type=int, default=60)
    p.add_argument("--hours", type=float, default=4)
    p = sub.add_parser("return", help="check the robots back in and settle the deposit")
    p.add_argument("booking_id")
    p.add_argument("--damage", action="append", default=[], help="robot=repair cost, e.g. M1=250 (repeatable)")
    p.add_argument("--late-days", type=int, default=0)
    sub.add_parser("rentals", help="every reservation and what is owed either way")
    sub.add_parser("availability", help="which robots are free on a day").add_argument("--date")
    for name in OPS:
        sub.choices[name].add_argument("--store", default=store)


def run_ops(a) -> int:
    try:
        c = load(a.store)
        _run(c, a)
        save(c, a.store)
        return 0
    except RentalError as e:
        print(f"refused: {e}")
        return 1


def _run(c: Counter, a):
    cmd = a.cmd
    if cmd == "reserve":
        day = _day(a.date)
        if day < date.today():
            raise RentalError(f"{day} is in the past")
        q = c.quote(
            a.job,
            day,
            a.km,
            rooms=a.rooms,
            heaviest=a.heaviest,
            stairs=a.stairs,
            sqft=a.sqft,
            detail=a.detail,
            guests=a.guests,
            hours=a.hours,
        )
        bid = c.book(q, a.customer)
        print(f"{bid}: {a.job} on {q['date']} for {a.customer}; robots {', '.join(q['robots'])} (~{q['est_hours']} h)")
        print(f"  charge ${q['total']:,.2f} now and hold a ${q['deposit']:,.0f} refundable deposit")
    elif cmd == "return":
        if a.booking_id not in c.bookings:
            raise RentalError(f"no booking {a.booking_id!r}")
        damages = {}
        for item in a.damage:
            rid, sep, cost = item.partition("=")
            try:
                damages[rid.strip()] = float(cost)
            except ValueError:
                raise RentalError(f"--damage must look like robot=cost, got {item!r}") from None
            if not sep or rid.strip() not in c.bookings[a.booking_id]["robots"]:
                raise RentalError(f"{rid.strip()!r} is not a robot on booking {a.booking_id}")
        b = c.return_robots(a.booking_id, damages, a.late_days)
        print(f"{a.booking_id} returned: damage ${b['damage']:,.2f}, late fee ${b['late_fee']:,.2f}")
        print(
            f"  refund ${b['deposit_refund']:,.2f} of the deposit"
            + (f"; bill ${b['extra_due']:,.2f} extra" if b["extra_due"] else "")
        )
    elif cmd == "rentals":
        for bid, b in c.bookings.items():
            if b["status"] == "booked":
                money = f"holding ${b['deposit']:,.0f} deposit"
            else:
                money = f"refund ${b['deposit_refund']:,.2f}" + (
                    f", bill ${b['extra_due']:,.2f}" if b["extra_due"] else ""
                )
            print(f"{bid}  {b['status']:<9}{b['date']}  {b['customer']:<16}{b['job']:<11}${b['total']:>9,.2f}  {money}")
        if not c.bookings:
            print("no reservations yet")
    else:
        day = _day(a.date)
        free = {r.robot_id for r in c.available(day)}
        for r in c.fleet.values():
            print(f"{r.robot_id:<5}{r.model:<16}{r.kind:<10}{'free' if r.robot_id in free else 'reserved'}")
