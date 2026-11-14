"""The auction engine: bid validation, ranking, extensions and closing.

Every function that changes an auction runs inside one database transaction with
the RFQ row locked (SELECT ... FOR UPDATE), so two bids on the same auction are
processed strictly one after the other.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app.errors import BusinessRuleError, NotFoundError
from app.models import ActivityLog, AuctionStatus, Bid, EventType, Rfq, Supplier, TriggerType
from app.schemas import BidCreate

TRIGGER_REASONS = {
    TriggerType.BID_RECEIVED: "Bid received",
    TriggerType.ANY_RANK_CHANGE: "Supplier ranking changed",
    TriggerType.L1_CHANGE: "Lowest bidder (L1) changed",
}


def get_auction_status(rfq: Rfq, now: datetime) -> AuctionStatus:
    if now < rfq.bid_start_time:
        return AuctionStatus.SCHEDULED
    if now < rfq.current_close_time:
        return AuctionStatus.ACTIVE
    # Extensions pushed the close all the way to the hard limit.
    if rfq.current_close_time >= rfq.forced_close_time:
        return AuctionStatus.FORCE_CLOSED
    return AuctionStatus.CLOSED


def compute_ranking(db: Session, rfq_id: int) -> list[Bid]:
    """Each supplier's current (latest) bid, ordered so index 0 is L1.

    Ties on total amount go to whoever submitted that price first.
    """
    latest_bid_ids = (
        select(func.max(Bid.id))
        .where(Bid.rfq_id == rfq_id)
        .group_by(Bid.supplier_id)
    )
    return list(
        db.scalars(
            select(Bid)
            .where(Bid.id.in_(latest_bid_ids))
            .order_by(Bid.total_amount, Bid.created_at, Bid.id)
        )
    )


def ranks_by_supplier(ranking: list[Bid]) -> dict[int, int]:
    return {bid.supplier_id: position for position, bid in enumerate(ranking, start=1)}


def submit_bid(db: Session, rfq_id: int, data: BidCreate) -> tuple[Bid, int, bool]:
    """Validate and store a bid, then apply the auction's extension rule.

    Returns (bid, supplier's new rank, whether the auction was extended).
    """
    # Lock the RFQ row until commit. A concurrent bid on the same RFQ waits here,
    # so it sees the ranking and close time this bid leaves behind.
    # populate_existing makes SQLAlchemy overwrite any copy of the RFQ already in
    # this session with the row we just locked, so we never act on stale data.
    rfq = db.scalar(
        select(Rfq)
        .where(Rfq.id == rfq_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if rfq is None:
        raise NotFoundError("RFQ not found")

    # Read the clock only after we hold the lock: if we waited for another bid,
    # we must judge this one by when it is actually processed.
    now = clock.utc_now()
    _check_auction_open(rfq, now)

    supplier = db.get(Supplier, data.supplier_id)
    if supplier is None:
        raise BusinessRuleError("Supplier not found")
    if data.quote_validity_date < now.date():
        raise BusinessRuleError("Quote validity date cannot be in the past")

    total = data.total_amount
    previous_bid = _latest_bid_of_supplier(db, rfq.id, supplier.id)
    if previous_bid is not None and total >= previous_bid.total_amount:
        raise BusinessRuleError(
            f"New bid ({total:,.2f}) must be lower than your previous bid "
            f"({previous_bid.total_amount:,.2f})"
        )

    ranking_before = compute_ranking(db, rfq.id)

    bid = Bid(
        rfq_id=rfq.id,
        supplier_id=supplier.id,
        carrier_name=data.carrier_name,
        freight_charges=data.freight_charges,
        origin_charges=data.origin_charges,
        destination_charges=data.destination_charges,
        total_amount=total,
        transit_time_days=data.transit_time_days,
        quote_validity_date=data.quote_validity_date,
        created_at=now,
    )
    db.add(bid)
    db.flush()  # assigns bid.id so the new bid is included in the ranking query

    ranking_after = compute_ranking(db, rfq.id)
    ranks_before = ranks_by_supplier(ranking_before)
    ranks_after = ranks_by_supplier(ranking_after)
    new_rank = ranks_after[supplier.id]

    l1_before = ranking_before[0].supplier_id if ranking_before else None
    l1_after = ranking_after[0].supplier_id
    rank_changed = ranks_before != ranks_after
    l1_changed = l1_before != l1_after

    _log(
        db, rfq, EventType.BID_SUBMITTED, now,
        f"{supplier.name} submitted {total:,.2f} (carrier: {bid.carrier_name}) "
        f"and is now L{new_rank}.",
    )
    if rank_changed:
        _log(db, rfq, EventType.RANK_CHANGED, now, "Ranking: " + _describe_ranking(ranking_after))
    if l1_changed:
        if l1_before is None:
            message = f"{supplier.name} is L1 with the first bid."
        else:
            previous_l1 = ranking_before[0].supplier.name
            message = f"{ranking_after[0].supplier.name} took L1 from {previous_l1}."
        _log(db, rfq, EventType.L1_CHANGED, now, message)

    extended = _apply_extension(db, rfq, now, rank_changed, l1_changed)

    db.commit()
    return bid, new_rank, extended


def close_expired_auctions(db: Session) -> int:
    """Record the closing event for auctions whose close time has passed.

    Bid acceptance never depends on this; it only keeps the activity log complete.
    Returns how many auctions were closed.
    """
    now = clock.utc_now()
    # SKIP LOCKED: if a bid is mid-transaction on an RFQ, skip it this round
    # rather than wait. The bid may even extend it, so we re-check next round.
    expired = db.scalars(
        select(Rfq)
        .where(Rfq.closed_at.is_(None), Rfq.current_close_time <= now)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    ).all()

    for rfq in expired:
        rfq.closed_at = rfq.current_close_time
        ranking = compute_ranking(db, rfq.id)
        result = (
            f"Winning bid: {ranking[0].supplier.name} at {ranking[0].total_amount:,.2f}."
            if ranking
            else "No bids were received."
        )
        if get_auction_status(rfq, now) == AuctionStatus.FORCE_CLOSED:
            _log(db, rfq, EventType.AUCTION_FORCE_CLOSED, rfq.current_close_time,
                 f"Auction force closed at the forced close time. {result}")
        else:
            _log(db, rfq, EventType.AUCTION_CLOSED, rfq.current_close_time,
                 f"Auction closed. {result}")

    db.commit()
    return len(expired)


def _check_auction_open(rfq: Rfq, now: datetime) -> None:
    if now < rfq.bid_start_time:
        raise BusinessRuleError("Auction has not started yet")
    # current_close_time can never exceed forced_close_time, so the first check
    # is a safety net; it also gives the clearer message once the hard limit passes.
    if now >= rfq.forced_close_time:
        raise BusinessRuleError("Auction has been force closed")
    if now >= rfq.current_close_time:
        raise BusinessRuleError("Auction is closed")


def _apply_extension(
    db: Session, rfq: Rfq, now: datetime, rank_changed: bool, l1_changed: bool
) -> bool:
    if not rfq.british_auction_enabled:
        return False

    previous_close = rfq.current_close_time
    # The window is measured back from the *current* close time, so after an
    # extension the window moves forward with it.
    window_start = previous_close - timedelta(minutes=rfq.trigger_window_minutes)
    if now < window_start:
        return False

    triggered = {
        TriggerType.BID_RECEIVED: True,  # we only get here for an accepted bid
        TriggerType.ANY_RANK_CHANGE: rank_changed,
        TriggerType.L1_CHANGE: l1_changed,
    }[rfq.trigger_type]
    if not triggered:
        return False

    if previous_close >= rfq.forced_close_time:
        return False  # already at the hard limit; nothing left to extend

    new_close = min(
        previous_close + timedelta(minutes=rfq.extension_minutes),
        rfq.forced_close_time,
    )
    rfq.current_close_time = new_close

    message = (
        f"{TRIGGER_REASONS[rfq.trigger_type]} within the last "
        f"{rfq.trigger_window_minutes} min of closing. "
    )
    if new_close == rfq.forced_close_time:
        message += "Auction extended up to the forced close time; no further extensions possible."
    else:
        message += f"Auction extended by {rfq.extension_minutes} min."

    _log(db, rfq, EventType.AUCTION_EXTENDED, now, message,
         previous_close_time=previous_close, new_close_time=new_close)
    return True


def _latest_bid_of_supplier(db: Session, rfq_id: int, supplier_id: int) -> Bid | None:
    return db.scalar(
        select(Bid)
        .where(Bid.rfq_id == rfq_id, Bid.supplier_id == supplier_id)
        .order_by(Bid.id.desc())
        .limit(1)
    )


def _describe_ranking(ranking: list[Bid]) -> str:
    return ", ".join(
        f"L{position} {bid.supplier.name} ({bid.total_amount:,.2f})"
        for position, bid in enumerate(ranking, start=1)
    )


def _log(
    db: Session,
    rfq: Rfq,
    event_type: EventType,
    at: datetime,
    message: str,
    previous_close_time: datetime | None = None,
    new_close_time: datetime | None = None,
) -> None:
    db.add(
        ActivityLog(
            rfq_id=rfq.id,
            event_type=event_type,
            message=message,
            previous_close_time=previous_close_time,
            new_close_time=new_close_time,
            created_at=at,
        )
    )
