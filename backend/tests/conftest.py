import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

# Point the app at the test database before any app module creates the engine.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/rfq_auction_test"
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import clock  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Supplier, TriggerType  # noqa: E402
from app.schemas import BidCreate, RfqCreate  # noqa: E402
from app.services.rfq_service import create_rfq  # noqa: E402

# 17:00 UTC; default auction runs 17:00 -> 18:00, forced close 18:30.
T0 = datetime(2026, 3, 10, 17, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, now: datetime):
        self.now = now

    def set(self, hour: int, minute: int, second: int = 0) -> None:
        self.now = T0.replace(hour=hour, minute=minute, second=second)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE activity_logs, bids, rfqs, suppliers RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        db.add_all([Supplier(name=name) for name in ["Alpha", "Bravo", "Charlie", "Delta"]])
        db.commit()


@pytest.fixture(autouse=True)
def fake_clock(monkeypatch):
    fake = FakeClock(T0 - timedelta(hours=1))  # RFQs are created before the auction starts
    monkeypatch.setattr(clock, "utc_now", fake)
    return fake


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    # Not used as a context manager, so the background closer loop doesn't start.
    return TestClient(app)


def rfq_payload(**overrides) -> dict:
    payload = {
        "reference_id": "RFQ-001",
        "name": "Chennai to Hamburg FCL",
        "pickup_date": "2026-03-20",
        "bid_start_time": T0.isoformat(),
        "bid_close_time": (T0 + timedelta(hours=1)).isoformat(),
        "forced_close_time": (T0 + timedelta(minutes=90)).isoformat(),
        "british_auction_enabled": True,
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "trigger_type": "BID_RECEIVED",
    }
    payload.update(overrides)
    return payload


def make_auction(db, trigger=TriggerType.BID_RECEIVED, forced_close=None, **overrides) -> int:
    payload = rfq_payload(trigger_type=trigger, **overrides)
    if forced_close is not None:
        payload["forced_close_time"] = forced_close.isoformat()
    return create_rfq(db, RfqCreate(**payload)).id


def bid(supplier_id: int, freight: str, origin: str = "0", destination: str = "0", **overrides) -> BidCreate:
    data = {
        "supplier_id": supplier_id,
        "carrier_name": "Maersk",
        "freight_charges": Decimal(freight),
        "origin_charges": Decimal(origin),
        "destination_charges": Decimal(destination),
        "transit_time_days": 20,
        "quote_validity_date": date(2026, 4, 30),
    }
    data.update(overrides)
    return BidCreate(**data)


ALPHA, BRAVO, CHARLIE, DELTA = 1, 2, 3, 4
