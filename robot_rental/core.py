"""Fleet, job-based quoting, bookings and returns for robot rentals."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from datetime import date

__all__ = ["Robot", "FLEET", "Counter", "RentalError", "job_requirements"]

KM_RATE = 2.5
OPERATOR_HOURLY = 45.0


class RentalError(Exception):
    pass


@dataclass
class Robot:
    robot_id: str
    model: str
    kind: str
    daily: float
    deposit: float
    lift_kg: float = 0
    stairs: bool = False
    sqft_per_hour: float = 0
    serves_per_hour: float = 0
    needs_operator: bool = False
    booked: set = field(default_factory=set)


FLEET = [
    Robot(
        "H-01", "Humanoid H2", "humanoid", 650, 2000, lift_kg=25, stairs=True, sqft_per_hour=300, needs_operator=True
    ),
    Robot(
        "H-02", "Humanoid H2", "humanoid", 650, 2000, lift_kg=25, stairs=True, sqft_per_hour=300, needs_operator=True
    ),
    Robot("C-01", "CargoMate 200", "cargo", 220, 800, lift_kg=200, stairs=True),
    Robot("C-02", "CargoMate 120", "cargo", 160, 600, lift_kg=120, stairs=False),
    Robot("K-01", "ScrubPro X", "cleaner", 140, 400, sqft_per_hour=1500),
    Robot("K-02", "ScrubPro X", "cleaner", 140, 400, sqft_per_hour=1500),
    Robot("S-01", "ServeBot", "server", 120, 300, serves_per_hour=60),
    Robot("S-02", "ServeBot", "server", 120, 300, serves_per_hour=60),
    Robot("S-03", "ServeBot", "server", 120, 300, serves_per_hour=60),
]


def job_requirements(job: str, **p) -> dict:
    if job == "move":
        return {
            "needs": [
                {"kind": "cargo", "lift_kg": p.get("heaviest", 50), "stairs": p.get("stairs", False)},
                {"kind": "humanoid"} if p.get("rooms", 1) >= 3 else None,
            ],
            "hours": 1.5 * p.get("rooms", 1) + (1 if p.get("stairs") else 0),
        }
    if job == "deep_clean":
        sqft = p.get("sqft", 1000)
        return {
            "needs": [{"kind": "cleaner", "sqft": sqft}, {"kind": "humanoid"} if p.get("detail") else None],
            "hours": sqft / 1500,
        }
    if job == "event":
        guests, hours = p.get("guests", 50), p.get("hours", 4)
        servers = max(1, math.ceil(guests / 60 / max(hours, 1) * 2))  # ~2 serves per guest across the event
        return {"needs": [{"kind": "server"} for _ in range(servers)], "hours": hours}
    raise RentalError(f"unknown job {job!r}")


def _fits(r: Robot, need: dict) -> bool:
    if r.kind != need["kind"]:
        return False
    if r.lift_kg < need.get("lift_kg", 0):
        return False
    return not (need.get("stairs") and not r.stairs)


class Counter:
    def __init__(self, fleet: list[Robot] | None = None):
        self.fleet = {
            r.robot_id: r
            for r in (fleet or [Robot(**{k: v for k, v in r.__dict__.items() if k != "booked"}) for r in FLEET])
        }
        self.bookings: dict[str, dict] = {}
        self._ids = itertools.count(1)

    def available(self, day: date) -> list[Robot]:
        return [r for r in self.fleet.values() if day not in r.booked]

    def quote(self, job: str, day: date, km: float = 10, **params) -> dict:
        req = job_requirements(job, **params)
        free = sorted(self.available(day), key=lambda r: r.daily)
        chosen = []
        for need in [n for n in req["needs"] if n]:
            pick = next((r for r in free if _fits(r, need) and r not in chosen), None)
            if not pick:
                raise RentalError(f"no {need['kind']} robot available on {day} for {need}")
            chosen.append(pick)
        hours = round(req["hours"], 2)
        rental = sum(r.daily for r in chosen)
        delivery = round(km * KM_RATE * 2, 2)
        operator = round(OPERATOR_HOURLY * hours, 2) if any(r.needs_operator for r in chosen) else 0.0
        deposit = sum(r.deposit for r in chosen)
        return {
            "job": job,
            "date": day.isoformat(),
            "robots": [r.robot_id for r in chosen],
            "est_hours": hours,
            "rental": rental,
            "delivery": delivery,
            "operator": operator,
            "total": round(rental + delivery + operator, 2),
            "deposit": deposit,
        }

    def book(self, q: dict, customer: str) -> str:
        day = date.fromisoformat(q["date"])
        for rid in q["robots"]:
            if day in self.fleet[rid].booked:
                raise RentalError(f"{rid} already booked on {day}")
        for rid in q["robots"]:
            self.fleet[rid].booked.add(day)
        bid = f"R{next(self._ids):04d}"
        self.bookings[bid] = {**q, "customer": customer, "status": "booked"}
        return bid

    def return_robots(self, booking_id: str, damages: dict[str, float] | None = None, late_days: int = 0) -> dict:
        b = self.bookings[booking_id]
        if b["status"] != "booked":
            raise RentalError("booking not active")
        damage = sum((damages or {}).values())
        late = late_days * b["rental"]
        charged = min(b["deposit"], damage + late)
        b.update(
            status="returned",
            damage=damage,
            late_fee=late,
            deposit_refund=b["deposit"] - charged,
            extra_due=max(0, damage + late - b["deposit"]),
        )
        for rid in b["robots"]:
            self.fleet[rid].booked.discard(date.fromisoformat(b["date"]))
        return b
