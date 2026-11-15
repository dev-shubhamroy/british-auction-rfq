from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models import AuctionStatus, EventType, TriggerType

# Largest value a NUMERIC(12, 2) column can hold.
MAX_AMOUNT = Decimal("9999999999.99")


class RfqCreate(BaseModel):
    reference_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    pickup_date: date
    # AwareDatetime rejects timestamps without a timezone, so we never have to
    # guess which timezone the client meant.
    bid_start_time: AwareDatetime
    bid_close_time: AwareDatetime
    forced_close_time: AwareDatetime

    british_auction_enabled: bool = True
    trigger_window_minutes: int | None = Field(default=None, ge=1, le=1440)
    extension_minutes: int | None = Field(default=None, ge=1, le=1440)
    trigger_type: TriggerType | None = None

    @model_validator(mode="after")
    def check_times_and_config(self):
        self.reference_id = self.reference_id.strip()
        self.name = self.name.strip()
        if not self.reference_id or not self.name:
            raise ValueError("RFQ name and reference ID are required")

        if self.bid_close_time <= self.bid_start_time:
            raise ValueError("Bid close time must be after bid start time")
        if self.forced_close_time <= self.bid_close_time:
            raise ValueError("Forced close time must be after bid close time")
        # Compared with the close date in UTC, since that's how times are stored.
        if self.pickup_date < self.bid_close_time.astimezone(timezone.utc).date():
            raise ValueError("Pickup / service date cannot be before the bid close date")

        if self.british_auction_enabled:
            if self.trigger_window_minutes is None or self.extension_minutes is None:
                raise ValueError("Trigger window (X) and extension duration (Y) are required")
            if self.trigger_type is None:
                raise ValueError("Extension trigger type is required")
        else:
            self.trigger_window_minutes = None
            self.extension_minutes = None
            self.trigger_type = None
        return self


class BidCreate(BaseModel):
    supplier_id: int
    carrier_name: str = Field(min_length=1, max_length=200)
    freight_charges: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    origin_charges: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    destination_charges: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    transit_time_days: int = Field(ge=1, le=365)
    quote_validity_date: date

    @model_validator(mode="after")
    def check_carrier_and_total(self):
        self.carrier_name = self.carrier_name.strip()
        if not self.carrier_name:
            raise ValueError("Carrier name is required")
        # Each charge fits the column on its own, but their sum might not.
        if self.total_amount > MAX_AMOUNT:
            raise ValueError(f"Total quote cannot exceed {MAX_AMOUNT:,}")
        return self

    @property
    def total_amount(self) -> Decimal:
        return self.freight_charges + self.origin_charges + self.destination_charges


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class RfqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_id: str
    name: str
    pickup_date: date
    bid_start_time: datetime
    bid_close_time: datetime
    current_close_time: datetime
    forced_close_time: datetime
    british_auction_enabled: bool
    trigger_window_minutes: int | None
    extension_minutes: int | None
    trigger_type: TriggerType | None
    created_at: datetime


class RfqListItem(RfqOut):
    status: AuctionStatus
    lowest_bid: Decimal | None
    bid_count: int


class RfqListResponse(BaseModel):
    server_time: datetime
    items: list[RfqListItem]


class BidOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    supplier_name: str
    carrier_name: str
    freight_charges: Decimal
    origin_charges: Decimal
    destination_charges: Decimal
    total_amount: Decimal
    transit_time_days: int
    quote_validity_date: date
    created_at: datetime

    @classmethod
    def from_bid(cls, bid) -> "BidOut":
        return cls(
            id=bid.id,
            supplier_id=bid.supplier_id,
            supplier_name=bid.supplier.name,
            carrier_name=bid.carrier_name,
            freight_charges=bid.freight_charges,
            origin_charges=bid.origin_charges,
            destination_charges=bid.destination_charges,
            total_amount=bid.total_amount,
            transit_time_days=bid.transit_time_days,
            quote_validity_date=bid.quote_validity_date,
            created_at=bid.created_at,
        )


class RankingRow(BidOut):
    rank: int


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: EventType
    message: str
    previous_close_time: datetime | None
    new_close_time: datetime | None
    created_at: datetime


class RfqDetail(BaseModel):
    server_time: datetime
    rfq: RfqOut
    status: AuctionStatus
    lowest_bid: Decimal | None
    extension_count: int
    rankings: list[RankingRow]
    bids: list[BidOut]
    activity: list[ActivityLogOut]


class BidResult(BaseModel):
    bid: BidOut
    rank: int
    extended: bool
    current_close_time: datetime
