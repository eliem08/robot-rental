<!-- sell-kit:start -->
# Robot Rental

[![CI](https://github.com/eliem08/robot-rental/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/robot-rental/actions/workflows/ci.yml)

> **Rent a robot for a move, a deep clean or an event.**

**Who it's for:** Robot fleet operators, and the people booking them for one-off jobs.

**The problem:** Robots are expensive to own and hard to book, and quoting a job by hand is slow and error-prone.

**What you get:** Job-based quotes that pick the right robots, availability-safe booking, deposits, damage and late-fee returns.

## Quickstart

Customers receive a release archive with the wheel and the examples. Python 3.10+ and no other dependencies.

```bash
pip install robot_rental-0.1.0-py3-none-any.whl
robot-rental fleet
robot-rental quote move --rooms 3 --heaviest 80 --stairs --date 2026-11-07 --km 12
robot-rental quote event --guests 120 --hours 5 --date 2026-11-07
robot-rental book move --rooms 3 --heaviest 80 --stairs --date 2026-11-07 --km 12 --customer acme
robot-rental return R0001 --damages "scratched brush=150" --late-days 1
```

## Web app and API

Every command is also a JSON API endpoint and a browser form, served by the built-in web app.

```bash
robot-rental-web --port 8000          # then open http://127.0.0.1:8000
robot-rental-web keys create --label "first customer"   # prints an API key (stored hashed)
docker build -t robot-rental . && docker run -p 8000:8000 -e API_KEYS=sk_... -v robot-rental-data:/data robot-rental
```

Every API call needs `Authorization: Bearer <key>` once any key exists; a server on a public address refuses to start without one. Calls are rate-limited per key (60/min, `--rate`) and metered: `robot-rental-web usage` prints calls per key for billing.

Endpoints: `POST /api/fleet`, `POST /api/quote`, plus `GET /healthz` and `GET /api/spec` (machine-readable field list).
Files are sent as `{"name": ..., "content": ...}`, folders as `{"files": [...]}` or a base64 zip.

## Deploy and sell

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eliem08/robot-rental)

`render.yaml` (one click, above) and `fly.toml` (`fly launch --copy-config`) both run the Dockerfile with a persistent `/data` volume and a `/healthz` check.
To sell self-serve, set four variables and point a Stripe webhook at `https://<your-host>/billing/webhook` (events `checkout.session.completed` and `customer.subscription.deleted`):

| Variable | Example |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRICES` | `operator=price_123,fleet=price_456` |
| `PUBLIC_URL` | `https://robot-rental.example.com` |

Buyers pick a plan on `/pricing`, pay on Stripe Checkout and see their API key once on the success page. Cancelling the subscription revokes the key. A selling server always requires a key.

## Pricing

Every plan starts with a 14-day free trial. Prices in USD, billed monthly unless noted.

| Plan | Price | Includes |
|---|---|---|
| **Operator** | $149 per month | Quotes and bookings; Deposits and returns |
| **Fleet** | $599 per month | Everything in Operator; Fleet onboarding support |
| **Marketplace** | Custom (revenue share, contact sales) | Everything in Fleet; Multi-operator support |

To start a trial or buy a plan, [request access](https://github.com/eliem08/robot-rental/issues/new?title=Robot%20Rental%20trial&labels=sales).

Plan note, owner decision on merge: there is no feature gating by plan in the code — every API key unlocks the same software (fleet, quote, book, return). The fleet is a fixed 9-robot list in code, so Operator's "up to 20 robots" and Fleet's "unlimited robots" are not enforced or configurable; Fleet's custom job types and reporting, and Marketplace's multi-operator marketplace and payments, are not built and have been removed from the sales copy. Higher tiers differ by human onboarding/support, not by gated features. Marketplace is contact-sales, not a Stripe plan, so the STRIPE_PRICES example only lists operator/fleet.

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
robot-rental book move --rooms 3 --heaviest 80 --stairs --date 2026-11-07 --km 12 --customer acme
robot-rental return R0001 --damages "scratched brush=150" --late-days 1
```

Bookings are stored in `~/.robot-rental/bookings.json` (or `$ROBOT_RENTAL_HOME/bookings.json`); a quote reads that file, so a booked robot is not offered again for the same date. The web app runs the CLI with `HOME` set to its data dir, so web bookings persist in the server's data dir.

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
python -m pip wheel . --no-deps -w dist            # customer wheel, as in Quickstart
```

```
robot_rental/core.py       domain logic (pure, importable, fully tested)
robot_rental/__main__.py   CLI (`robot-rental ...` / `python -m robot_rental ...`)
tests/                unit tests + generated CLI smoke tests
```

CI runs lint and tests on Ubuntu and Windows across Python 3.10, 3.12 and 3.13.
Design, data model, trade-offs and production path: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

Part of the [agent-economy](https://github.com/eliem08/agent-economy) portfolio (idea #25).
