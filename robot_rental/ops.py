"""Operating commands: reservations, returns and availability on a persistent store (also served by the web app).

The fleet starts as the built-in demo list. The first `robot-add` replaces it with your own robots only.

Charges and deposits are a ledger: `rentals` shows what each customer owes or is due back. Taking the
payment and holding the deposit is done through your own payment provider.
"""

import itertools
import json
import os
import re
from dataclasses import asdict
from datetime import date

from .core import BUILT_IN_JOBS, KM_RATE, OPERATOR_HOURLY, Counter, RentalError, Robot

OPS = (
    "robot-add",
    "robot-remove",
    "robots",
    "job-add",
    "job-remove",
    "jobs",
    "rates",
    "reserve",
    "return",
    "rentals",
    "availability",
)
KINDS = ("humanoid", "cargo", "cleaner", "server")  # built-in kinds; your own robots can use any name
KIND_RE = re.compile(r"^[a-z][a-z0-9_-]{0,30}$")


def _day(text) -> date:
    try:
        return date.fromisoformat(text) if text else date.today()
    except ValueError:
        raise RentalError(f"{text!r} is not a date like 2026-12-01") from None


def load(path: str) -> Counter:
    try:
        with open(path, encoding="utf-8-sig") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return Counter()
    if not isinstance(doc, dict) or not isinstance(doc.get("bookings"), dict):
        raise RentalError(f"{path}: not a robot-rental store")
    if "robots" in doc:  # the operator's own fleet (possibly empty); otherwise the demo fleet
        c = Counter([Robot(**r) for r in doc["robots"]])
        c.own_fleet = True
    else:
        c = Counter()
    c.bookings = doc["bookings"]
    c.custom_jobs = dict(doc.get("jobs", {}))
    rates = doc.get("rates", {})
    c.km_rate = float(rates.get("km_rate", KM_RATE))
    c.operator_hourly = float(rates.get("operator_hourly", OPERATOR_HOURLY))
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
        doc = {"bookings": c.bookings, "next_id": next_id}
        if getattr(c, "own_fleet", False):
            doc["robots"] = [{k: v for k, v in asdict(r).items() if k != "booked"} for r in c.fleet.values()]
        if c.custom_jobs:
            doc["jobs"] = c.custom_jobs
        if (c.km_rate, c.operator_hourly) != (KM_RATE, OPERATOR_HOURLY):
            doc["rates"] = {"km_rate": c.km_rate, "operator_hourly": c.operator_hourly}
        json.dump(doc, fh, indent=2)
    os.replace(tmp, path)


def add_ops(sub):
    store = os.environ.get("ROBOT_RENTAL_STORE", "rentals.json")
    p = sub.add_parser("robot-add", help="add one of your robots to the fleet (the first one replaces the demo)")
    p.add_argument("robot_id")
    p.add_argument("--model", required=True)
    p.add_argument("--kind", required=True, help=f"{', '.join(KINDS)} or your own, e.g. security")
    p.add_argument("--daily", type=float, required=True, help="rental price per day")
    p.add_argument("--deposit", type=float, required=True)
    p.add_argument("--lift-kg", type=float, default=0)
    p.add_argument("--stairs", action="store_true", help="can climb stairs")
    p.add_argument("--sqft-per-hour", type=float, default=0, help="cleaning rate")
    p.add_argument("--serves-per-hour", type=float, default=0)
    p.add_argument("--needs-operator", action="store_true", help="must be supervised by a paid operator")
    sub.add_parser("robot-remove", help="take a robot out of the fleet").add_argument("robot_id")
    sub.add_parser("robots", help="the fleet, and whether it is your own or the demo")
    p = sub.add_parser("job-add", help="define a job type you rent out: which robots, and how long it takes")
    p.add_argument("name", help="e.g. warehouse_inventory")
    p.add_argument(
        "--robot",
        action="append",
        required=True,
        help="KIND[:COUNT[:MIN_LIFT_KG]], repeatable, e.g. cargo:2:100 or humanoid",
    )
    p.add_argument("--hours", type=float, default=0, help="fixed hours per job")
    p.add_argument("--hours-per-unit", type=float, default=0, help="extra hours per unit (see --unit)")
    p.add_argument("--unit", default="unit", help="what a unit is, e.g. pallet, room, 1000 sqft")
    p.add_argument("--description", default="")
    sub.add_parser("job-remove", help="delete one of your job types").add_argument("name")
    sub.add_parser("jobs", help="built-in and your own job types")
    p = sub.add_parser("rates", help="show or set your delivery and operator rates")
    p.add_argument("--km-rate", type=float, help="delivery price per km, each way")
    p.add_argument("--operator-hourly", type=float, help="operator price per hour")
    p = sub.add_parser("reserve", help="price a job and reserve the robots for that day")
    p.add_argument("customer")
    p.add_argument("job", help="move, deep_clean, event or one of your own (see jobs)")
    p.add_argument("--date", help="YYYY-MM-DD, default today")
    p.add_argument("--km", type=float, default=10, help="delivery distance one way")
    p.add_argument("--rooms", type=int, default=2)
    p.add_argument("--heaviest", type=float, default=50, help="heaviest item in kg (move)")
    p.add_argument("--stairs", action="store_true")
    p.add_argument("--sqft", type=float, default=1200)
    p.add_argument("--detail", action="store_true", help="detailed clean")
    p.add_argument("--guests", type=int, default=60)
    p.add_argument("--hours", type=float, default=4)
    p.add_argument("--units", type=float, default=1, help="units of work for your own job types")
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


def _job_line(spec: dict) -> str:
    robots = ", ".join(
        f"{r['count']}x {r['kind']}" + (f" (lifts {r['lift_kg']:g} kg)" if r.get("lift_kg") else "")
        for r in spec["robots"]
    )
    hours = " + ".join(
        x
        for x in (
            f"{spec['hours']:g} h" if spec.get("hours") else "",
            f"{spec['hours_per_unit']:g} h per {spec.get('unit', 'unit')}" if spec.get("hours_per_unit") else "",
        )
        if x
    )
    return f"{robots}; {hours}"


def _run(c: Counter, a):
    cmd = a.cmd
    if cmd == "job-add":
        name = a.name.strip()
        if not KIND_RE.match(name) or name in BUILT_IN_JOBS:
            raise RentalError(f"job name {name!r} must be lowercase letters, digits, - or _ and not built in")
        robots = []
        for item in a.robot:
            parts = item.split(":")
            try:
                kind, count = parts[0].strip(), int(parts[1]) if len(parts) > 1 and parts[1] else 1
                lift = float(parts[2]) if len(parts) > 2 else 0
            except ValueError:
                raise RentalError(f"--robot {item!r} must look like cargo:2:100") from None
            if not KIND_RE.match(kind) or not 1 <= count <= 50 or lift < 0 or len(parts) > 3:
                raise RentalError(f"--robot {item!r} must look like cargo:2:100")
            robots.append({"kind": kind, "count": count, **({"lift_kg": lift} if lift else {})})
        for name_, v in (("hours", a.hours), ("hours-per-unit", a.hours_per_unit)):
            if not 0 <= v <= 24:
                raise RentalError(f"--{name_} must be between 0 and 24")
        if not a.hours and not a.hours_per_unit:
            raise RentalError("give --hours, --hours-per-unit or both")
        missing = sorted({r["kind"] for r in robots} - {r.kind for r in c.fleet.values()})
        c.custom_jobs[name] = {
            "robots": robots,
            "hours": a.hours,
            "hours_per_unit": a.hours_per_unit,
            "unit": a.unit,
            "description": a.description,
        }
        print(f"job {name}: {_job_line(c.custom_jobs[name])}")
        if missing:
            print(f"note: no {', '.join(missing)} robot in the fleet yet; quotes fail until you add one")
    elif cmd == "job-remove":
        if a.name not in c.custom_jobs:
            raise RentalError(f"no job type {a.name!r} of your own")
        del c.custom_jobs[a.name]
        print(f"removed job {a.name}")
    elif cmd == "jobs":
        print(
            "built in: move (--rooms, --heaviest, --stairs), deep_clean (--sqft, --detail), event (--guests, --hours)"
        )
        for name, spec in sorted(c.custom_jobs.items()):
            print(f"  {name:<20} {_job_line(spec)}" + (f"  - {spec['description']}" if spec.get("description") else ""))
        if not c.custom_jobs:
            print("no job types of your own yet: add one with job-add")
    elif cmd == "rates":
        for name, v in (("km-rate", a.km_rate), ("operator-hourly", a.operator_hourly)):
            if v is not None and not 0 <= v <= 100_000:
                raise RentalError(f"--{name} must be between 0 and 100000")
        if a.km_rate is not None:
            c.km_rate = a.km_rate
        if a.operator_hourly is not None:
            c.operator_hourly = a.operator_hourly
        print(f"delivery ${c.km_rate:,.2f}/km each way; operator ${c.operator_hourly:,.2f}/h")
    elif cmd == "robot-add":
        if not getattr(c, "own_fleet", False):
            if any(b["status"] == "booked" for b in c.bookings.values()):
                raise RentalError("bookings on the demo fleet are still out; return them before adding your own robots")
            c.fleet, c.own_fleet = {}, True
            print("replacing the demo fleet with your own robots")
        kind = a.kind.strip().lower()
        if not KIND_RE.match(kind):
            raise RentalError(f"--kind {a.kind!r} must be lowercase letters, digits, - or _")
        rid = a.robot_id.strip()
        if not rid or rid in c.fleet:
            raise RentalError(f"robot id {rid!r} is empty or already in the fleet")
        for name in ("daily", "deposit"):
            if not getattr(a, name) > 0:
                raise RentalError(f"--{name} must be > 0")
        for name in ("lift_kg", "sqft_per_hour", "serves_per_hour"):
            if not getattr(a, name) >= 0:
                raise RentalError(f"--{name.replace('_', '-')} cannot be negative")
        c.fleet[rid] = Robot(
            rid,
            a.model,
            kind,
            a.daily,
            a.deposit,
            a.lift_kg,
            a.stairs,
            a.sqft_per_hour,
            a.serves_per_hour,
            a.needs_operator,
        )
        print(f"{rid}: {a.model} ({kind}) at ${a.daily:,.0f}/day, deposit ${a.deposit:,.0f}; {len(c.fleet)} in fleet")
    elif cmd == "robot-remove":
        if a.robot_id not in c.fleet:
            raise RentalError(f"no robot {a.robot_id!r} in the fleet")
        out = [bid for bid, b in c.bookings.items() if b["status"] == "booked" and a.robot_id in b["robots"]]
        if out:
            raise RentalError(f"{a.robot_id} is on booking(s) {', '.join(out)}; return them first")
        if not getattr(c, "own_fleet", False):
            c.fleet = {k: v for k, v in c.fleet.items()}
            c.own_fleet = True
        del c.fleet[a.robot_id]
        print(f"{a.robot_id} removed; {len(c.fleet)} in fleet")
    elif cmd == "robots":
        print("your fleet" if getattr(c, "own_fleet", False) else "demo fleet (add your own with robot-add)")
        for r in c.fleet.values():
            caps = ", ".join(
                x
                for x in (
                    f"lifts {r.lift_kg:g} kg" if r.lift_kg else "",
                    "stairs" if r.stairs else "",
                    f"{r.sqft_per_hour:g} sqft/h" if r.sqft_per_hour else "",
                    f"{r.serves_per_hour:g} serves/h" if r.serves_per_hour else "",
                    "needs operator" if r.needs_operator else "",
                )
                if x
            )
            print(f"  {r.robot_id:<8}{r.model:<18}{r.kind:<10}${r.daily:>6,.0f}/day  {caps}")
        if not c.fleet:
            print("  (empty)")
    elif cmd == "reserve":
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
            units=a.units,
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
