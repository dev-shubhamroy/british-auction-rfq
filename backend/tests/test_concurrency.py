"""Concurrent bids on the same auction, each in its own session/connection,
just like two simultaneous HTTP requests."""

import threading
import time

from sqlalchemy import select

from app.database import SessionLocal
from app.errors import BusinessRuleError
from app.models import Bid, Rfq, TriggerType
from app.services.auction_service import submit_bid
from tests.conftest import ALPHA, BRAVO, T0, bid, make_auction


def run_concurrently(rfq_id, bids):
    """Submit all bids at the same moment from separate threads."""
    barrier = threading.Barrier(len(bids))
    results = [None] * len(bids)

    def worker(index, data):
        with SessionLocal() as session:
            barrier.wait()
            try:
                results[index] = submit_bid(session, rfq_id, data)[2]
            except BusinessRuleError as exc:
                results[index] = exc

    threads = [threading.Thread(target=worker, args=(i, b)) for i, b in enumerate(bids)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    return results


def test_two_simultaneous_bids_both_extend(db, fake_clock):
    # Without the row lock both transactions would read close = 18:00 and both
    # write 18:05, losing one extension.
    rfq_id = make_auction(db, TriggerType.BID_RECEIVED)
    fake_clock.set(17, 55)

    results = run_concurrently(rfq_id, [bid(ALPHA, "1000"), bid(BRAVO, "990")])

    assert results == [True, True]
    db.expire_all()
    assert db.get(Rfq, rfq_id).current_close_time == T0.replace(hour=18, minute=10)


def test_duplicate_simultaneous_bid_is_accepted_once(db, fake_clock):
    rfq_id = make_auction(db)
    fake_clock.set(17, 30)

    results = run_concurrently(rfq_id, [bid(ALPHA, "1000"), bid(ALPHA, "1000")])

    assert sorted(type(r).__name__ for r in results) == ["BusinessRuleError", "bool"]
    assert len(db.scalars(select(Bid).where(Bid.rfq_id == rfq_id)).all()) == 1


def test_bid_waits_for_lock_held_by_another_transaction(db, fake_clock):
    rfq_id = make_auction(db)
    fake_clock.set(17, 30)

    holder = SessionLocal()
    holder.scalar(select(Rfq).where(Rfq.id == rfq_id).with_for_update())

    finished = threading.Event()

    def place_bid():
        with SessionLocal() as session:
            submit_bid(session, rfq_id, bid(ALPHA, "1000"))
        finished.set()

    thread = threading.Thread(target=place_bid)
    thread.start()
    time.sleep(0.5)
    assert not finished.is_set(), "bid should be blocked while the RFQ row is locked"

    holder.commit()  # releases the lock
    holder.close()
    thread.join(timeout=5)
    assert finished.is_set()
