import argparse
import sys
from datetime import date

from .core import FLEET, Counter, RentalError


def main(argv=None):
    ap = argparse.ArgumentParser(prog="robot-rental")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fleet")
    q = sub.add_parser("quote")
    q.add_argument("job", choices=["move", "deep_clean", "event"])
    q.add_argument("--date", default=date.today().isoformat())
    q.add_argument("--km", type=float, default=10)
    q.add_argument("--rooms", type=int, default=2)
    q.add_argument("--heaviest", type=float, default=50)
    q.add_argument("--stairs", action="store_true")
    q.add_argument("--sqft", type=float, default=1200)
    q.add_argument("--detail", action="store_true")
    q.add_argument("--guests", type=int, default=60)
    q.add_argument("--hours", type=float, default=4)
    a = ap.parse_args(argv)
    if a.cmd == "fleet":
        for r in FLEET:
            print(f"{r.robot_id:<5} {r.model:<15} {r.kind:<9} ${r.daily:>4.0f}/day deposit ${r.deposit:,.0f}"
                  + ("  (operator)" if r.needs_operator else ""))
        return 0
    c = Counter()
    try:
        res = c.quote(a.job, date.fromisoformat(a.date), a.km, rooms=a.rooms, heaviest=a.heaviest, stairs=a.stairs,
                      sqft=a.sqft, detail=a.detail, guests=a.guests, hours=a.hours)
    except RentalError as e:
        print(f"Can't quote: {e}", file=sys.stderr)
        return 1
    print(f"{res['job']} on {res['date']}: robots {', '.join(res['robots'])} (~{res['est_hours']} h)")
    for k in ("rental", "delivery", "operator"):
        print(f"  {k:<10} ${res[k]:>8,.2f}")
    print(f"  {'total':<10} ${res['total']:>8,.2f}   + refundable deposit ${res['deposit']:,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
