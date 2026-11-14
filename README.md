# British Auction RFQ System

An RFQ (Request for Quotation) system where suppliers compete in a British-style
reverse auction. Bids near the end of an auction extend its close time, up to a fixed
forced close time. Built for the GoComet full stack internship assignment.

Design notes, the architecture diagram and the database schema are in
[docs/DESIGN.md](docs/DESIGN.md).

## Features

- Create an RFQ with bid start, bid close, forced close and pickup dates, and configure
  the auction: trigger window (X minutes), extension (Y minutes) and the trigger type
  (any bid, any rank change, or L1 change in the last X minutes).
- Suppliers submit quotes with carrier, freight/origin/destination charges, transit time
  and validity. Quotes are ranked L1, L2, ... by total charges.
- Auctions extend repeatedly when the trigger fires, never past the forced close time.
- Auction list with lowest bid, current and forced close times, and status
  (Scheduled / Active / Closed / Force Closed).
- Auction details page with rankings, bid history, auction settings, a bid form and an
  activity log that records every extension and its reason.

## Tech stack

- Backend: Python 3.12, FastAPI, Pydantic, SQLAlchemy 2.0
- Database: PostgreSQL 16
- Frontend: React, Vite, Tailwind CSS, React Router
- Tests: pytest, run against a real PostgreSQL database

## Project structure

```
backend/
  app/
    main.py           app setup, error handlers, background task that closes auctions
    models.py         SQLAlchemy models
    schemas.py        request/response models and validation
    routes/           API endpoints
    services/
      auction_service.py   bidding, ranking, extensions, closing
      rfq_service.py       creating and reading RFQs
    seed.py           demo suppliers and a sample auction
  tests/
frontend/
  src/
    pages/            AuctionList, AuctionDetails, CreateRfq
    components/
    api.js            API calls
docs/DESIGN.md
docker-compose.yml    optional PostgreSQL container
```

## Setup

You need Python 3.12, Node 20+ and PostgreSQL 16.

Start PostgreSQL, either with Docker:

```bash
docker compose up -d
```

or with Homebrew:

```bash
brew install postgresql@16
brew services start postgresql@16
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
```

Create the databases. With Docker, `rfq_auction` already exists, so only the test
database is needed:

```bash
docker compose exec postgres createdb -U postgres rfq_auction_test
```

With Homebrew (the default superuser is your macOS user, so create the `postgres`
role first or adjust the URLs in `.env`):

```bash
createuser -s postgres
createdb -U postgres rfq_auction
createdb -U postgres rfq_auction_test
```

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.seed
```

Frontend:

```bash
cd frontend
npm install
```

## Environment variables

Set in `backend/.env` (see `backend/.env.example`):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres@localhost:5432/rfq_auction` | Main database |
| `TEST_DATABASE_URL` | `postgresql+psycopg://postgres@localhost:5432/rfq_auction_test` | Used by the tests |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

With the Docker setup, include the password: `postgresql+psycopg://postgres:postgres@localhost:5432/...`.

## Running

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the backend.
API docs are at http://localhost:8000/docs.

## Tests

```bash
cd backend && source .venv/bin/activate && pytest
```

The tests recreate the tables in the test database on each run and use a fake clock,
so time-based rules (trigger windows, closing, forced close) are tested at exact
timestamps.
