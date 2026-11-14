from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import BidCreate, BidOut, BidResult, RfqCreate, RfqDetail, RfqListResponse, RfqOut
from app.services import auction_service, rfq_service

router = APIRouter(prefix="/api/rfqs", tags=["rfqs"])


@router.post("", response_model=RfqOut, status_code=status.HTTP_201_CREATED)
def create_rfq(data: RfqCreate, db: Session = Depends(get_db)):
    return rfq_service.create_rfq(db, data)


@router.get("", response_model=RfqListResponse)
def list_rfqs(db: Session = Depends(get_db)):
    return rfq_service.list_rfqs(db)


@router.get("/{rfq_id}", response_model=RfqDetail)
def get_rfq(rfq_id: int, db: Session = Depends(get_db)):
    return rfq_service.get_rfq_detail(db, rfq_id)


@router.post("/{rfq_id}/bids", response_model=BidResult, status_code=status.HTTP_201_CREATED)
def submit_bid(rfq_id: int, data: BidCreate, db: Session = Depends(get_db)):
    bid, rank, extended = auction_service.submit_bid(db, rfq_id, data)
    return BidResult(
        bid=BidOut.from_bid(bid),
        rank=rank,
        extended=extended,
        current_close_time=bid.rfq.current_close_time,
    )
