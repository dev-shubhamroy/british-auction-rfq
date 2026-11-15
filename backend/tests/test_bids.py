import pytest

from app.errors import BusinessRuleError
from app.services.auction_service import compute_ranking, submit_bid
from tests.conftest import ALPHA, BRAVO, CHARLIE, DELTA, bid, make_auction

VALID_BID = {
    "supplier_id": ALPHA,
    "carrier_name": "Maersk",
    "freight_charges": "1000.50",
    "origin_charges": "100",
    "destination_charges": "49.50",
    "transit_time_days": 18,
    "quote_validity_date": "2026-04-30",
}


@pytest.fixture
def rfq_id(db, fake_clock):
    rfq_id = make_auction(db)
    fake_clock.set(17, 10)  # auction is active, outside the trigger window
    return rfq_id


def test_submit_bid(client, rfq_id):
    response = client.post(f"/api/rfqs/{rfq_id}/bids", json=VALID_BID)

    assert response.status_code == 201
    body = response.json()
    assert body["rank"] == 1
    assert body["extended"] is False
    assert body["bid"]["total_amount"] == "1150.00"  # freight + origin + destination
    assert body["bid"]["supplier_name"] == "Alpha"

    events = [log["event_type"] for log in client.get(f"/api/rfqs/{rfq_id}").json()["activity"]]
    assert events == ["L1_CHANGED", "RANK_CHANGED", "BID_SUBMITTED", "RFQ_CREATED"]


@pytest.mark.parametrize(
    "field, value",
    [
        ("freight_charges", "0"),
        ("freight_charges", "-10"),
        ("origin_charges", "-1"),
        ("destination_charges", "-0.01"),
        ("freight_charges", "10.123"),  # more than 2 decimal places
        ("carrier_name", "   "),
        ("transit_time_days", 0),
        ("quote_validity_date", "not-a-date"),
    ],
)
def test_invalid_bid_fields_are_rejected(client, rfq_id, field, value):
    response = client.post(f"/api/rfqs/{rfq_id}/bids", json={**VALID_BID, field: value})
    assert response.status_code == 422


@pytest.mark.parametrize("missing", ["carrier_name", "freight_charges", "transit_time_days", "quote_validity_date"])
def test_missing_required_fields_are_rejected(client, rfq_id, missing):
    payload = {k: v for k, v in VALID_BID.items() if k != missing}
    assert client.post(f"/api/rfqs/{rfq_id}/bids", json=payload).status_code == 422


def test_quote_validity_in_the_past_is_rejected(client, rfq_id):
    response = client.post(f"/api/rfqs/{rfq_id}/bids", json={**VALID_BID, "quote_validity_date": "2026-03-09"})
    assert response.status_code == 400


def test_unknown_supplier_and_rfq(client, rfq_id):
    assert client.post(f"/api/rfqs/{rfq_id}/bids", json={**VALID_BID, "supplier_id": 99}).status_code == 400
    assert client.post("/api/rfqs/999/bids", json=VALID_BID).status_code == 404


def test_bid_before_start_is_rejected(client, db, fake_clock):
    rfq_id = make_auction(db)
    fake_clock.set(16, 59, 59)

    response = client.post(f"/api/rfqs/{rfq_id}/bids", json=VALID_BID)

    assert response.status_code == 400
    assert response.json()["detail"] == "Auction has not started yet"


def test_bid_exactly_at_start_is_accepted(db, fake_clock):
    rfq_id = make_auction(db)
    fake_clock.set(17, 0)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))


@pytest.mark.parametrize("hour, minute, second", [(18, 0, 0), (18, 0, 1), (18, 20, 0), (18, 45, 0)])
def test_bid_at_or_after_close_is_rejected(client, db, fake_clock, hour, minute, second):
    rfq_id = make_auction(db)
    fake_clock.set(hour, minute, second)

    response = client.post(f"/api/rfqs/{rfq_id}/bids", json=VALID_BID)

    assert response.status_code == 400
    assert response.json()["detail"] == "Auction is closed"


def test_bid_just_before_close_is_accepted(db, fake_clock):
    rfq_id = make_auction(db)
    fake_clock.set(17, 59, 59)
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))


def test_supplier_must_lower_own_bid(db, rfq_id):
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))

    with pytest.raises(BusinessRuleError, match="must be lower than your previous bid"):
        submit_bid(db, rfq_id, bid(ALPHA, "1000"))  # same amount (also blocks double submits)
    with pytest.raises(BusinessRuleError):
        submit_bid(db, rfq_id, bid(ALPHA, "1200"))

    submit_bid(db, rfq_id, bid(ALPHA, "999.99"))


def test_supplier_does_not_have_to_beat_l1(db, rfq_id):
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    _, rank, _ = submit_bid(db, rfq_id, bid(BRAVO, "1500"))
    assert rank == 2


def test_rankings_l1_l2_l3(client, db, rfq_id):
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    submit_bid(db, rfq_id, bid(BRAVO, "800", origin="100"))   # 900
    submit_bid(db, rfq_id, bid(CHARLIE, "700", destination="400"))  # 1100
    submit_bid(db, rfq_id, bid(DELTA, "950"))

    rankings = client.get(f"/api/rfqs/{rfq_id}").json()["rankings"]

    assert [(r["rank"], r["supplier_name"], r["total_amount"]) for r in rankings] == [
        (1, "Bravo", "900.00"),
        (2, "Delta", "950.00"),
        (3, "Alpha", "1000.00"),
        (4, "Charlie", "1100.00"),
    ]


def test_ranking_uses_each_suppliers_latest_bid(client, db, rfq_id):
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    submit_bid(db, rfq_id, bid(BRAVO, "900"))
    submit_bid(db, rfq_id, bid(ALPHA, "850"))

    detail = client.get(f"/api/rfqs/{rfq_id}").json()

    assert [r["supplier_name"] for r in detail["rankings"]] == ["Alpha", "Bravo"]
    assert detail["lowest_bid"] == "850.00"
    # bid history keeps every bid, sorted by price
    assert [b["total_amount"] for b in detail["bids"]] == ["850.00", "900.00", "1000.00"]


def test_tie_goes_to_earlier_bid(db, rfq_id, fake_clock):
    submit_bid(db, rfq_id, bid(ALPHA, "1000"))
    fake_clock.set(17, 11)
    submit_bid(db, rfq_id, bid(BRAVO, "1000"))

    assert [b.supplier_id for b in compute_ranking(db, rfq_id)] == [ALPHA, BRAVO]

    # Alpha re-quotes to match a later lower price: Bravo got there first.
    submit_bid(db, rfq_id, bid(BRAVO, "900"))
    fake_clock.set(17, 12)
    submit_bid(db, rfq_id, bid(ALPHA, "900"))
    assert [b.supplier_id for b in compute_ranking(db, rfq_id)] == [BRAVO, ALPHA]


def test_total_larger_than_the_column_is_rejected(client, rfq_id):
    # Each charge fits NUMERIC(12,2) on its own, but the sum would not.
    payload = {
        **VALID_BID,
        "freight_charges": "9999999999.99",
        "origin_charges": "9999999999.99",
        "destination_charges": "9999999999.99",
    }
    response = client.post(f"/api/rfqs/{rfq_id}/bids", json=payload)
    assert response.status_code == 422
    assert "Total quote cannot exceed" in response.text


def test_largest_total_that_fits_is_accepted(client, rfq_id):
    payload = {**VALID_BID, "freight_charges": "9999999999.00", "origin_charges": "0.99", "destination_charges": "0"}
    assert client.post(f"/api/rfqs/{rfq_id}/bids", json=payload).status_code == 201


def test_quote_must_be_valid_until_pickup_date(client, rfq_id):
    # Default RFQ pickup date is 2026-03-20.
    response = client.post(f"/api/rfqs/{rfq_id}/bids", json={**VALID_BID, "quote_validity_date": "2026-03-19"})
    assert response.status_code == 400
    assert "pickup" in response.json()["detail"]

    response = client.post(f"/api/rfqs/{rfq_id}/bids", json={**VALID_BID, "quote_validity_date": "2026-03-20"})
    assert response.status_code == 201
