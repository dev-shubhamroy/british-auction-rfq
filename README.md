# British Auction RFQ System

A simplified RFQ (Request for Quotation) system where suppliers compete in a
**British (reverse) auction**: bids are open, suppliers keep lowering their price,
activity near the end extends the auction automatically, and a hard **forced close
time** stops bidding no matter what.

- **Backend:** Python 3.12 · FastAPI · Pydantic · SQLAlchemy 2.0 · PostgreSQL
- **Frontend:** React 19 · Vite · Tailwind CSS · React Router
- **Docs:** [Design (HLD, schema, algorithms)](docs/DESIGN.md) ·
  [Interview preparation guide](docs/INTERVIEW_PREPARATION.md)

## Features

- Create an RFQ with reference ID, name, pickup date, bid start / close / forced close
  times, and the British auction config: trigger window **X**, extension **Y**, and
  one of three triggers:
  1. bid received in the last X minutes
  2. any supplier rank change in the last X minutes
  3. lowest bidder (L1) change in the last X minutes
- Submit quotes (carrier, freight / origin / destination charges, transit time,
  quote validity). Ranking L1, L2, L3… by total = freight + origin + destination.
- Repeated extensions measured from the *current* close time, always capped at the
  forced close time.
- Row-level locking so simultaneous bids can't corrupt the close time or ranking.
- Auction list (lowest bid, current close, forced close, status) and auction details
  (rankings, full bid history, quote details, X/Y config, activity log with the reason
  for every extension). Pages refresh automatically.

## Project layout

```
backend/
  app/
    main.py                 FastAPI app, error handlers, background closer loop
    config.py               settings from environment / .env
    database.py             engine, session, Base
    clock.py                utc_now() — single source of time (patched in tests)
    models.py               rfqs, suppliers, bids, activity_logs
    schemas.py              Pydantic request/response models + validation
    errors.py               NotFoundError / ConflictError / BusinessRuleError
    routes/                 rfqs.py, suppliers.py (HTTP layer only)
    services/
      auction_service.py    bid validation, ranking, extensions, closing  <- core logic
      rfq_service.py        create / list / detail queries
    seed.py                 demo suppliers + one live demo auction
  tests/                    53 pytest tests against a real PostgreSQL test DB
frontend/
  src/
    api.js                  fetch wrapper for /api
    format.js               money/date formatting, UTC <-> local helpers
    pages/                  AuctionList, AuctionDetails, CreateRfq
    components/             BidForm, Countdown, StatusBadge, Card, FormField
docs/
  DESIGN.md
  INTERVIEW_PREPARATION.md
docker-compose.yml          optional PostgreSQL via Docker
```

## Running locally (macOS / zsh)

Prerequisites: Python 3.12, Node 20+, and PostgreSQL 16 (Homebrew **or** Docker).

### 1. Start PostgreSQL

**Option A — Homebrew**

```bash
brew install postgresql@16
```

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
initdb -D .pgdata -U postgres --auth=trust -E UTF8
```

```bash
LC_ALL=en_US.UTF-8 pg_ctl -D .pgdata -l .pgdata/server.log start
```

(`LC_ALL` avoids a macOS locale startup error. `.pgdata/` is git-ignored.)
Alternatively, `brew services start postgresql@16` runs it as a background service.

**Option B — Docker**

```bash
docker compose up -d
```

Then create the two databases (app + tests):

```bash
psql -U postgres -h localhost -c "CREATE DATABASE rfq_auction;" -c "CREATE DATABASE rfq_auction_test;"
```

(With Docker, `rfq_auction` already exists; only the second command is needed, and
psql may need `PGPASSWORD=postgres`.)

### 2. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

`python -m app.seed` creates the tables, five demo suppliers, and one live demo
auction (only if there are no RFQs yet). API docs: http://localhost:8000/docs

If you use Docker Postgres, change the URLs in `.env` to
`postgresql+psycopg://postgres:postgres@localhost:5432/...`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `localhost:8000`.

### 4. Tests

```bash
cd backend && source .venv/bin/activate && pytest -q
```

The tests use the `rfq_auction_test` database (override with `TEST_DATABASE_URL`) and
drop/recreate its tables on each run. Time is controlled with a fake clock, so the
tests run instantly and deterministically.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/suppliers` | Suppliers for the bid form |
| POST | `/api/rfqs` | Create RFQ + auction config |
| GET | `/api/rfqs` | Auction listing |
| GET | `/api/rfqs/{id}` | Auction details (rankings, bids, config, activity) |
| POST | `/api/rfqs/{id}/bids` | Submit a bid |

## Key decisions (short version)

- **Status is derived from timestamps**, not stored: `now < start` → Scheduled,
  `now < current_close` → Active, closed at forced close → Force Closed, else Closed.
  Bid acceptance therefore never depends on a scheduler.
- **No Redis/Celery.** The only scheduled work is writing the "auction closed" log
  entry, done by a 5-second asyncio loop inside the API process.
- **`SELECT ... FOR UPDATE` on the RFQ row** serialises bids per auction; the clock is
  read *after* the lock is acquired.
- **Money is `NUMERIC(12,2)`**, timestamps are `timestamptz` in UTC, and the API
  rejects timestamps without a timezone.

See [docs/DESIGN.md](docs/DESIGN.md) for the full design and assumptions.

## Known limitations

- No authentication: the supplier is picked from a dropdown, standing in for a
  logged-in supplier account.
- Live updates use 5-second polling rather than WebSockets.
- Schema is created with `create_all`; there are no Alembic migrations.
- Single currency (shown as INR); no minimum bid decrement rule.
