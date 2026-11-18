<!-- sell-kit:start -->
# Robot Rental

[![CI](https://github.com/eliem08/robot-rental/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/robot-rental/actions/workflows/ci.yml)

> **Rent a robot for a move, a deep clean or an event.**

**Who it's for:** Robot fleet operators, and the people booking them for one-off jobs.

**The problem:** Robots are expensive to own and hard to book, and quoting a job by hand is slow and error-prone.

**What you get:** Your own fleet, job types and rates; quotes that pick the right robots, availability-safe booking, deposits, damage and late-fee returns.

## Quickstart

Customers receive a release archive with the wheel and the examples. Python 3.10+ and no other dependencies.

```bash
pip install robot_rental-0.1.0-py3-none-any.whl
robot-rental robots --store rentals.json
robot-rental reserve "Ana Diaz" move --date 2099-01-10 --rooms 3 --stairs --store rentals.json
robot-rental availability --date 2099-01-10 --store rentals.json
```

## Web app and API

Every command is also a JSON API endpoint and a browser form, served by the built-in web app.

```bash
robot-rental-web --port 8000          # then open http://127.0.0.1:8000
robot-rental-web keys create --label "first customer"   # prints an API key (stored hashed)
docker build -t robot-rental . && docker run -p 8000:8000 -e API_KEYS=sk_... -v robot-rental-data:/data robot-rental
```

Every API call needs `Authorization: Bearer <key>` once any key exists; a server on a public address refuses to start without one. Calls are rate-limited per key (60/min, `--rate`) and metered: `robot-rental-web usage` prints calls per key for billing.

Endpoints: `POST /api/fleet`, `POST /api/quote`, `POST /api/robot-add`, `POST /api/robot-remove`, `POST /api/robots`, `POST /api/job-add`, `POST /api/job-remove`, `POST /api/jobs`, `POST /api/rates`, `POST /api/reserve`, `POST /api/return`, `POST /api/rentals`, `POST /api/availability`, plus `GET /healthz` and `GET /api/spec` (machine-readable field list).
Files are sent as `{"name": ..., "content": ...}`, folders as `{"files": [...]}` or a base64 zip.

## Deploy and sell

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eliem08/robot-rental)

`render.yaml` (one click, above) and `fly.toml` (`fly launch --copy-config`) both run the Dockerfile with a persistent `/data` volume and a `/healthz` check.
To sell self-serve, set four variables and point a Stripe webhook at `https://<your-host>/billing/webhook` (events `checkout.session.completed` and `customer.subscription.deleted`):

| Variable | Example |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRICES` | `team=price_123,business=price_456` |
| `PUBLIC_URL` | `https://robot-rental.example.com` |
| `PLAN_QUOTAS` (optional) | `team=10000,business=250000` successful calls per key per month |

Buyers pick a plan on `/pricing`, pay on Stripe Checkout and see their API key once on the success page. Cancelling the subscription revokes the key. A selling server always requires a key.

## Pricing

Monthly plans start with a 14-day free trial. Prices in USD, billed monthly unless noted.

| Plan | Price | Includes |
|---|---|---|
| **Operator** | $149 per month | Your own fleet, job types and rates; Quotes and bookings; Deposits and returns |
| **Fleet** | $599 per month | Rental and deposit ledger; Availability by day; Priority support |
| **Marketplace** | Custom (revenue share, contact sales) | Self-hosted deployment; Dedicated support |

To start a trial or buy a plan, [request access](https://github.com/eliem08/robot-rental/issues/new?title=Robot%20Rental%20trial&labels=sales).

Plan note: every plan runs the same software, and every API key unlocks all of it. Monthly call volumes are
enforced when `PLAN_QUOTAS` is set (see Deploy and sell); seat and agent limits are licence terms the code does
not enforce. Support, SLA and done-for-you items are services.

## Licence

Proprietary. Copyright (c) 2026 eliem08. All rights reserved. Use requires a paid plan or an active trial; see [LICENSE](LICENSE).
<!-- sell-kit:end -->

## What it does

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

## Your own fleet

The store starts with a built-in demo fleet. Add your own robots and the demo is replaced by them only:

```bash
robot-rental robot-add VAN-1 --model "Atlas Mover" --kind cargo --daily 300 --deposit 1000 --lift-kg 250 --stairs
robot-rental robot-add HB-1 --model "Unitree G1" --kind humanoid --daily 500 --deposit 3000 --needs-operator
robot-rental robots
robot-rental robot-remove VAN-1   # refused while the robot is on a booking
```

Quotes and reservations then use only your robots. `--kind` is any name you choose, so security, delivery or
drone robots work alongside the built-in humanoid, cargo, cleaner and server kinds.

## Your own jobs and rates

Besides the built-in move, deep_clean and event jobs, define the jobs you actually rent out. Each lists the
robots it needs (`KIND[:COUNT[:MIN_LIFT_KG]]`) and how long it takes: fixed hours, hours per unit, or both.

```bash
robot-rental job-add warehouse_inventory --robot cargo:2:200 --hours 1 --hours-per-unit 0.25 --unit pallet
robot-rental job-add night_patrol --robot security --hours 10
robot-rental rates --km-rate 3.20 --operator-hourly 60      # your delivery and operator prices
robot-rental jobs
robot-rental reserve acme warehouse_inventory --date 2027-01-10 --units 20 --km 15
```

Defaults until you set them: $2.50/km each way for delivery and $45/h for an operator.

## Roadmap

- Teleoperation fallback marketplace (remote operators take over hard steps)
- Insurance at checkout (pairs with agent-insure)
- Franchise depots + fleet utilisation dashboards

## Development

Zero runtime dependencies; Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m unittest discover -s tests -t .           # unit + CLI smoke tests
ruff check . && ruff format --check .               # lint + format
```

```
robot_rental/core.py       domain logic (pure, importable, fully tested)
robot_rental/__main__.py   CLI (`robot-rental ...` / `python -m robot_rental ...`)
tests/                unit tests + generated CLI smoke tests
```

CI runs lint and tests on Ubuntu and Windows across Python 3.10, 3.12 and 3.13.
Design, data model, trade-offs and production path: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

Part of the [agent-economy](https://github.com/eliem08/agent-economy) portfolio (idea #25).
