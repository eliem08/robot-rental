# robot-rental

> **Hertz for robots** — rent one for a move, a deep clean or an event.

Nobody needs to own a $40k humanoid to move apartments once. But renting one
for a Saturday? Yes. `robot-rental` is the booking engine for a robot rental
counter: fleet, job-based quoting, availability, delivery, operators,
deposits and return inspections.

## What the MVP does

- **Fleet**: robots with type (`humanoid`, `cargo`, `cleaner`, `server`),
  capabilities (`lift_kg`, `stairs`, `sqft_per_hour`, `serves_per_hour`), daily
  rate, operator requirement, depot
- **Job packages** → robot requirements and estimated hours:
  - `move`: rooms, heaviest item kg, stairs?
  - `deep_clean`: square feet
  - `event`: guests, hours
- **Quote**: picks the cheapest available robot combination meeting the
  requirements for the date, + delivery (per km from depot), + operator
  hours when required, + refundable damage deposit
- **Bookings** with per-day availability (no double booking)
- **Return inspection**: damage items charged against the deposit, late-return days

## Quickstart

```bash
pip install -e .
robot-rental fleet
robot-rental quote move --rooms 3 --heaviest 80 --stairs --date 2026-11-07 --km 12
robot-rental quote event --guests 120 --hours 5 --date 2026-11-07
```

## Roadmap

- Teleoperation fallback marketplace (remote operators take over hard steps)
- Insurance at checkout (pairs with agent-insure)
- Franchise depots + fleet utilisation dashboards
