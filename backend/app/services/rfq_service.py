import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import clock
from app.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import ActivityLog, Bid, EventType, Rfq, TriggerType
from app.schemas import (
    ActivityLogOut,
    BidOut,
    RankingRow,
    RfqCreate,
    RfqDetail,
    RfqListItem,
    RfqListResponse,
    RfqOut,
)
from app.services.auction_service import compute_ranking, get_auction_status

logger = logging.getLogger(__name__)

TRIGGER_LABELS = {
    TriggerType.BID_RECEIVED: "bid received",
    TriggerType.ANY_RANK_CHANGE: "any rank change",
    TriggerType.L1_CHANGE: "L1 change",
}


def create_rfq(db: Session, data: RfqCreate) -> Rfq:
    now = clock.utc_now()
    if data.bid_close_time <= now:
        raise BusinessRuleError("Bid close time must be in the future")
    if db.scalar(select(Rfq.id).where(Rfq.reference_id == data.reference_id)):
        raise ConflictError(f"An RFQ with reference ID '{data.reference_id}' already exists")

    rfq = Rfq(**data.model_dump(), current_close_time=data.bid_close_time)
    db.add(rfq)
    try:
        db.flush()
    except IntegrityError:
        # Two requests with the same reference ID raced past the check above.
        db.rollback()
        raise ConflictError(f"An RFQ with reference ID '{data.reference_id}' already exists")

    if rfq.british_auction_enabled:
        config = (
            f"British auction enabled: extend by {rfq.extension_minutes} min on "
            f"{TRIGGER_LABELS[rfq.trigger_type]} within the last "
            f"{rfq.trigger_window_minutes} min."
        )
    else:
        config = "British auction disabled: no automatic extensions."
    db.add(ActivityLog(rfq_id=rfq.id, event_type=EventType.RFQ_CREATED,
                       message=f"RFQ created. {config}", created_at=now))
    db.commit()
    logger.info("RFQ %s created (id %d)", rfq.reference_id, rfq.id)
    return rfq


def list_rfqs(db: Session) -> RfqListResponse:
    now = clock.utc_now()
    bid_stats = (
        select(
            Bid.rfq_id,
            func.min(Bid.total_amount).label("lowest_bid"),
            func.count(Bid.id).label("bid_count"),
        )
        .group_by(Bid.rfq_id)
        .subquery()
    )
    rows = db.execute(
        select(Rfq, bid_stats.c.lowest_bid, bid_stats.c.bid_count)
        .outerjoin(bid_stats, bid_stats.c.rfq_id == Rfq.id)
        .order_by(Rfq.created_at.desc(), Rfq.id.desc())
    ).all()

    items = [
        RfqListItem(
            **RfqOut.model_validate(rfq).model_dump(),
            status=get_auction_status(rfq, now),
            lowest_bid=lowest_bid,
            bid_count=bid_count or 0,
        )
        for rfq, lowest_bid, bid_count in rows
    ]
    return RfqListResponse(server_time=now, items=items)


def get_rfq_detail(db: Session, rfq_id: int) -> RfqDetail:
    now = clock.utc_now()
    rfq = db.get(Rfq, rfq_id)
    if rfq is None:
        raise NotFoundError("RFQ not found")

    ranking = compute_ranking(db, rfq.id)
    all_bids = db.scalars(
        select(Bid).where(Bid.rfq_id == rfq.id).order_by(Bid.total_amount, Bid.created_at, Bid.id)
    ).all()
    activity = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.rfq_id == rfq.id)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
    ).all()

    return RfqDetail(
        server_time=now,
        rfq=RfqOut.model_validate(rfq),
        status=get_auction_status(rfq, now),
        lowest_bid=ranking[0].total_amount if ranking else None,
        extension_count=sum(1 for log in activity if log.event_type == EventType.AUCTION_EXTENDED),
        rankings=[
            RankingRow(**BidOut.from_bid(bid).model_dump(), rank=position)
            for position, bid in enumerate(ranking, start=1)
        ],
        bids=[BidOut.from_bid(bid) for bid in all_bids],
        activity=[ActivityLogOut.model_validate(log) for log in activity],
    )
