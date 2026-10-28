import argparse
import contextlib
import csv
import itertools
import json
import math
import os
import pathlib
import sys
import tempfile
from datetime import date

from .core import FLEET, Counter, RentalError


def _finite_float(s: str) -> float:
    """argparse type: a float that is not nan/inf, so limits and prices cannot be bypassed."""
    v = float(s)
    if not math.isfinite(v):
        raise argparse.ArgumentTypeError(f"must be a finite number, got {s!r}")
    return v


def _store_path() -> pathlib.Path:
    # Computed at call time (not import time) so tests and the web app can
    # point it at a temp dir via the env var. The web app runs the CLI with
    # HOME=<data-dir>, so web bookings land in the server's data dir.
    return pathlib.Path(os.environ.get("ROBOT_RENTAL_HOME", pathlib.Path.home() / ".robot-rental")) / "bookings.json"


def _load() -> Counter:
    """A Counter restored from the bookings file, or a fresh one."""
    c = Counter()
    try:
        data = json.loads(_store_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return c
    bookings = data.get("bookings", {}) if isinstance(data, dict) else {}
    c.bookings = bookings
    max_id = 0
    for bid, b in bookings.items():
        if isinstance(b, dict) and b.get("status") == "booked":
            day = date.fromisoformat(b["date"])
            for rid in b.get("robots", []):
                if rid in c.fleet:
                    c.fleet[rid].booked.add(day)
        with contextlib.suppress(ValueError):
            max_id = max(max_id, int(str(bid).lstrip("R")))
    c._ids = itertools.count(max_id + 1)
    return c


def _save(c: Counter) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"bookings": c.bookings}
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _add_job_args(p):
    p.add_argument("job", choices=["move", "deep_clean", "event"])
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--km", type=_finite_float, default=10)
    p.add_argument("--rooms", type=int, default=2)
    p.add_argument("--heaviest", type=_finite_float, default=50)
    p.add_argument("--stairs", action="store_true")
    p.add_argument("--sqft", type=_finite_float, default=1200)
    p.add_argument("--detail", action="store_true")
    p.add_argument("--guests", type=int, default=60)
    p.add_argument("--hours", type=_finite_float, default=4)


def build_parser():
    ap = argparse.ArgumentParser(prog="robot-rental")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fleet")
    _add_job_args(sub.add_parser("quote"))
    b = sub.add_parser("book")
    _add_job_args(b)
    b.add_argument("--customer", required=True)
    r = sub.add_parser("return")
    r.add_argument("booking_id")
    r.add_argument("--late-days", type=int, default=0)
    r.add_argument("--damages", default="", help='e.g. "scratched brush=150, dented panel=200"')
    return ap


def _quote(c: Counter, a):
    return c.quote(
        a.job,
        date.fromisoformat(a.date),
        a.km,
        rooms=a.rooms,
        heaviest=a.heaviest,
        stairs=a.stairs,
        sqft=a.sqft,
        detail=a.detail,
        guests=a.guests,
        hours=a.hours,
    )


def _print_quote(res):
    print(f"{res['job']} on {res['date']}: robots {', '.join(res['robots'])} (~{res['est_hours']} h)")
    for k in ("rental", "delivery", "operator"):
        print(f"  {k:<10} ${res[k]:>8,.2f}")
    print(f"  {'total':<10} ${res['total']:>8,.2f}   + refundable deposit ${res['deposit']:,.0f}")


def _parse_damages(text: str) -> dict:
    damages = {}
    for item in (i.strip() for i in text.split(",") if i.strip()):
        if "=" not in item:
            raise ValueError(f"damages must be name=amount, got {item!r}")
        name, amount = item.split("=", 1)
        value = float(amount)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"damage amount must be a finite number >= 0, got {amount!r}")
        damages[name.strip()] = value
    return damages


def _run(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.cmd == "fleet":
        for r in FLEET:
            print(
                f"{r.robot_id:<5} {r.model:<15} {r.kind:<9} ${r.daily:>4.0f}/day deposit ${r.deposit:,.0f}"
                + ("  (operator)" if r.needs_operator else "")
            )
        return 0
    c = _load()
    if a.cmd == "quote":
        try:
            res = _quote(c, a)
        except RentalError as e:
            print(f"Can't quote: {e}", file=sys.stderr)
            return 1
        _print_quote(res)
        return 0
    if a.cmd == "book":
        try:
            res = _quote(c, a)
        except RentalError as e:
            print(f"Can't quote: {e}", file=sys.stderr)
            return 1
        bid = c.book(res, a.customer)
        _save(c)
        print(f"Booked {bid} for {a.customer}")
        _print_quote(res)
        return 0
    if a.cmd == "return":
        if a.booking_id not in c.bookings:
            print(f"No booking {a.booking_id}", file=sys.stderr)
            return 1
        try:
            damages = _parse_damages(a.damages)
            r = c.return_robots(a.booking_id, damages=damages, late_days=a.late_days)
        except RentalError as e:
            print(f"Can't return: {e}", file=sys.stderr)
            return 1
        _save(c)
        print(f"Returned {a.booking_id} (was {r['customer']})")
        print(f"  damage ${r['damage']:,.2f}  late fee ${r['late_fee']:,.2f}")
        print(f"  deposit refund ${r['deposit_refund']:,.2f}  extra due ${r['extra_due']:,.2f}")
        return 0
    return 2


def main(argv=None):
    """Run the CLI; a bad input file or argument exits 2 with a one-line error instead of a traceback.

    Set AGENT_ECONOMY_DEBUG=1 to see the full traceback.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        return _run(argv)
    except (OSError, ValueError, KeyError, csv.Error) as e:
        if os.environ.get("AGENT_ECONOMY_DEBUG"):
            raise
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e
        print(f"error: {msg}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
