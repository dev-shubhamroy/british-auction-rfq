from datetime import timedelta

from app.services.auction_service import close_expired_auctions, submit_bid
from tests.conftest import ALPHA, BRAVO, T0, bid, make_auction, rfq_payload


def test_create_rfq(client):
    response = client.post("/api/rfqs", json=rfq_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["reference_id"] == "RFQ-001"
    assert body["current_close_time"] == body["bid_close_time"]
    assert body["trigger_type"] == "BID_RECEIVED"

    detail = client.get(f"/api/rfqs/{body['id']}").json()
    assert detail["status"] == "SCHEDULED"
    assert [log["event_type"] for log in detail["activity"]] == ["RFQ_CREATED"]


def test_forced_close_must_be_after_bid_close(client):
    payload = rfq_payload(forced_close_time=(T0 + timedelta(hours=1)).isoformat())
    response = client.post("/api/rfqs", json=payload)
    assert response.status_code == 422
    assert "Forced close time must be after bid close time" in response.text


def test_bid_close_must_be_after_start(client):
    payload = rfq_payload(bid_close_time=T0.isoformat())
    assert client.post("/api/rfqs", json=payload).status_code == 422


def test_british_auction_requires_config(client):
    payload = rfq_payload(trigger_window_minutes=None)
    assert client.post("/api/rfqs", json=payload).status_code == 422


def test_british_auction_disabled_needs_no_config(client):
    payload = rfq_payload(
        british_auction_enabled=False,
        trigger_window_minutes=None,
        extension_minutes=None,
        trigger_type=None,
    )
    response = client.post("/api/rfqs", json=payload)
    assert response.status_code == 201
    assert response.json()["trigger_type"] is None


def test_timestamps_without_timezone_are_rejected(client):
    payload = rfq_payload(bid_start_time="2026-03-10T17:00:00")
    assert client.post("/api/rfqs", json=payload).status_code == 422


def test_close_time_in_the_past_is_rejected(client, fake_clock):
    fake_clock.set(18, 30)
    response = client.post("/api/rfqs", json=rfq_payload())
    assert response.status_code == 400


def test_duplicate_reference_id_is_rejected(client):
    assert client.post("/api/rfqs", json=rfq_payload()).status_code == 201
    response = client.post("/api/rfqs", json=rfq_payload(name="Another"))
    assert response.status_code == 409


def test_listing_shows_lowest_bid_and_status(client, db, fake_clock):
    rfq_id = make_auction(db)
    fake_clock.set(17, 10)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    submit_bid(db, rfq_id, bid(BRAVO, "900", origin="50"))

    items = client.get("/api/rfqs").json()["items"]

    assert len(items) == 1
    assert items[0]["status"] == "ACTIVE"
    assert items[0]["lowest_bid"] == "950.00"
    assert items[0]["bid_count"] == 2


def test_status_moves_through_lifecycle(client, db, fake_clock):
    rfq_id = make_auction(db)

    def status():
        return client.get(f"/api/rfqs/{rfq_id}").json()["status"]

    fake_clock.set(16, 59)
    assert status() == "SCHEDULED"
    fake_clock.set(17, 0)
    assert status() == "ACTIVE"
    fake_clock.set(18, 0)
    assert status() == "CLOSED"


def test_closer_logs_closing_event_once(db, fake_clock):
    rfq_id = make_auction(db)
    fake_clock.set(17, 10)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))

    fake_clock.set(17, 59)
    assert close_expired_auctions(db) == 0
    fake_clock.set(18, 0, 5)
    assert close_expired_auctions(db) == 1
    assert close_expired_auctions(db) == 0  # already closed, no duplicate event


def test_unknown_rfq_returns_404(client):
    assert client.get("/api/rfqs/999").status_code == 404
