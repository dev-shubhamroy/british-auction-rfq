"""Default auction: close 18:00, forced close 18:30, window X = 10 min, extension Y = 5 min."""

from datetime import datetime

from sqlalchemy import select

from app.models import ActivityLog, EventType, Rfq, TriggerType
from app.services.auction_service import close_expired_auctions, get_auction_status, submit_bid
from tests.conftest import ALPHA, BRAVO, CHARLIE, T0, bid, make_auction


def at(hour, minute, second=0) -> datetime:
    return T0.replace(hour=hour, minute=minute, second=second)


def close_time(db, rfq_id):
    db.expire_all()
    return db.get(Rfq, rfq_id).current_close_time


def extension_logs(db, rfq_id):
    return db.scalars(
        select(ActivityLog)
        .where(ActivityLog.rfq_id == rfq_id, ActivityLog.event_type == EventType.AUCTION_EXTENDED)
        .order_by(ActivityLog.id)
    ).all()


# ---------- trigger window ----------

def test_bid_outside_window_does_not_extend(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.BID_RECEIVED)
    fake_clock.set(17, 49, 59)

    _, _, extended = submit_bid(db, rfq_id, bid(ALPHA, "1000"))

    assert extended is False
    assert close_time(db, rfq_id) == at(18, 0)


def test_bid_at_window_start_extends(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.BID_RECEIVED)
    fake_clock.set(17, 50)

    _, _, extended = submit_bid(db, rfq_id, bid(ALPHA, "1000"))

    assert extended is True
    assert close_time(db, rfq_id) == at(18, 5)


# ---------- trigger a) bid received ----------

def test_bid_received_trigger(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.BID_RECEIVED)
    fake_clock.set(17, 30)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    fake_clock.set(17, 55)
    # Alpha only improves its own price: no rank change, still extends.
    submit_bid(db, rfq_id, bid(ALPHA, "990"))

    assert close_time(db, rfq_id) == at(18, 5)
    [log] = extension_logs(db, rfq_id)
    assert log.message.startswith("Bid received within the last 10 min")
    assert log.previous_close_time == at(18, 0)
    assert log.new_close_time == at(18, 5)


# ---------- trigger b) any rank change ----------

def test_any_rank_change_trigger(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.ANY_RANK_CHANGE)
    fake_clock.set(17, 30)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    submit_bid(db, rfq_id, bid(BRAVO, "1100"))

    # In window, but Bravo stays L2: no extension.
    fake_clock.set(17, 55)
    _, _, extended = submit_bid(db, rfq_id, bid(BRAVO, "1050"))
    assert extended is False
    assert close_time(db, rfq_id) == at(18, 0)

    # Bravo underbids Alpha: ranks swap, auction extends.
    fake_clock.set(17, 58)
    _, rank, extended = submit_bid(db, rfq_id, bid(BRAVO, "950"))
    assert (rank, extended) == (1, True)
    assert close_time(db, rfq_id) == at(18, 5)
    assert extension_logs(db, rfq_id)[0].message.startswith("Supplier ranking changed")


def test_any_rank_change_counts_new_supplier_below_l1(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.ANY_RANK_CHANGE)
    fake_clock.set(17, 30)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))

    fake_clock.set(17, 55)
    _, rank, extended = submit_bid(db, rfq_id, bid(BRAVO, "1500"))  # enters as L2

    assert (rank, extended) == (2, True)


# ---------- trigger c) L1 change ----------

def test_l1_change_trigger(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.L1_CHANGE)
    fake_clock.set(17, 30)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    submit_bid(db, rfq_id, bid(BRAVO, "1100"))
    submit_bid(db, rfq_id, bid(CHARLIE, "1200"))

    # Charlie overtakes Bravo (rank change) but Alpha is still L1: no extension.
    fake_clock.set(17, 55)
    _, rank, extended = submit_bid(db, rfq_id, bid(CHARLIE, "1050"))
    assert (rank, extended) == (2, False)
    assert close_time(db, rfq_id) == at(18, 0)

    # Charlie becomes the new L1: extends.
    fake_clock.set(17, 59)
    _, rank, extended = submit_bid(db, rfq_id, bid(CHARLIE, "990"))
    assert (rank, extended) == (1, True)
    assert close_time(db, rfq_id) == at(18, 5)
    assert extension_logs(db, rfq_id)[0].message.startswith("Lowest bidder (L1) changed")


def test_l1_improving_own_price_does_not_extend(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.L1_CHANGE)
    fake_clock.set(17, 30)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    fake_clock.set(17, 55)

    _, _, extended = submit_bid(db, rfq_id, bid(ALPHA, "900"))

    assert extended is False


# ---------- repeated extensions ----------

def test_repeated_extensions_use_current_close_time(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.BID_RECEIVED)

    fake_clock.set(17, 55)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    assert close_time(db, rfq_id) == at(18, 5)

    # 18:02 is after the original close, but inside the window of the new close (17:55-18:05).
    fake_clock.set(18, 2)
    submit_bid(db, rfq_id, bid(BRAVO, "990"))
    assert close_time(db, rfq_id) == at(18, 10)

    fake_clock.set(18, 9, 59)
    submit_bid(db, rfq_id, bid(ALPHA, "980"))
    assert close_time(db, rfq_id) == at(18, 15)

    assert len(extension_logs(db, rfq_id)) == 3


def test_extension_is_measured_from_close_time_not_bid_time(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.BID_RECEIVED)
    fake_clock.set(17, 51)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    assert close_time(db, rfq_id) == at(18, 5)  # 18:00 + 5, not 17:51 + 5


# ---------- forced close ----------

def test_extension_never_exceeds_forced_close(db, fake_clock):
    rfq_id = make_auction(db, TriggerType.BID_RECEIVED, forced_close=at(18, 8))

    fake_clock.set(17, 55)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    assert close_time(db, rfq_id) == at(18, 5)

    fake_clock.set(18, 1)
    _, _, extended = submit_bid(db, rfq_id, bid(BRAVO, "990"))
    assert extended is True
    assert close_time(db, rfq_id) == at(18, 8)  # 18:10 capped to 18:08
    assert "forced close time" in extension_logs(db, rfq_id)[-1].message

    # Already at the forced close: accepted, but no further extension or log.
    fake_clock.set(18, 7)
    _, _, extended = submit_bid(db, rfq_id, bid(ALPHA, "980"))
    assert extended is False
    assert close_time(db, rfq_id) == at(18, 8)
    assert len(extension_logs(db, rfq_id)) == 2


def test_force_closed_auction_rejects_bids_and_logs_force_close(client, db, fake_clock):
    rfq_id = make_auction(db, TriggerType.BID_RECEIVED, forced_close=at(18, 3))
    fake_clock.set(17, 58)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    assert close_time(db, rfq_id) == at(18, 3)

    fake_clock.set(18, 3)
    response = client.post(f"/api/rfqs/{rfq_id}/bids", json=bid(BRAVO, "900").model_dump(mode="json"))
    assert response.status_code == 400
    assert response.json()["detail"] == "Auction has been force closed"

    rfq = db.get(Rfq, rfq_id)
    assert get_auction_status(rfq, at(18, 3)).value == "FORCE_CLOSED"
    assert close_expired_auctions(db) == 1
    last_event = db.scalars(
        select(ActivityLog).where(ActivityLog.rfq_id == rfq_id).order_by(ActivityLog.id.desc())
    ).first()
    assert last_event.event_type == EventType.AUCTION_FORCE_CLOSED
    assert last_event.created_at == at(18, 3)


def test_no_extension_when_british_auction_disabled(db, fake_clock):
    rfq_id = make_auction(
        db, british_auction_enabled=False,
        trigger=None, trigger_window_minutes=None, extension_minutes=None,
    )
    fake_clock.set(17, 59)

    _, _, extended = submit_bid(db, rfq_id, bid(ALPHA, "1000"))

    assert extended is False
    assert close_time(db, rfq_id) == at(18, 0)
