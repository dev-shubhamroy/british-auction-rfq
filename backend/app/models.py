import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TriggerType(str, enum.Enum):
    BID_RECEIVED = "BID_RECEIVED"
    ANY_RANK_CHANGE = "ANY_RANK_CHANGE"
    L1_CHANGE = "L1_CHANGE"


class AuctionStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    FORCE_CLOSED = "FORCE_CLOSED"


class EventType(str, enum.Enum):
    RFQ_CREATED = "RFQ_CREATED"
    BID_SUBMITTED = "BID_SUBMITTED"
    RANK_CHANGED = "RANK_CHANGED"
    L1_CHANGED = "L1_CHANGED"
    AUCTION_EXTENDED = "AUCTION_EXTENDED"
    AUCTION_CLOSED = "AUCTION_CLOSED"
    AUCTION_FORCE_CLOSED = "AUCTION_FORCE_CLOSED"


Money = Numeric(12, 2)


class Rfq(Base):
    __tablename__ = "rfqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    pickup_date: Mapped[date] = mapped_column(Date)

    bid_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The close time the buyer originally set. Never changes after creation.
    bid_close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The close time in effect right now. Starts equal to bid_close_time and is
    # pushed forward by extensions, but never past forced_close_time.
    current_close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forced_close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    british_auction_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger_window_minutes: Mapped[int | None] = mapped_column(Integer)  # X
    extension_minutes: Mapped[int | None] = mapped_column(Integer)  # Y
    trigger_type: Mapped[TriggerType | None] = mapped_column(
        Enum(TriggerType, native_enum=False, create_constraint=True, length=20)
    )

    # Set by the background closer once the auction has ended and the closing
    # event has been logged. Bid validation never looks at this column.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    bids: Mapped[list["Bid"]] = relationship(back_populates="rfq")
    activity_logs: Mapped[list["ActivityLog"]] = relationship(back_populates="rfq")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (
        Index("ix_bids_rfq_supplier", "rfq_id", "supplier_id"),
        # Matches the ranking and bid history order, and the per-RFQ lowest bid.
        Index("ix_bids_rfq_total", "rfq_id", "total_amount", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    carrier_name: Mapped[str] = mapped_column(String(200))
    freight_charges: Mapped[Decimal] = mapped_column(Money)
    origin_charges: Mapped[Decimal] = mapped_column(Money)
    destination_charges: Mapped[Decimal] = mapped_column(Money)
    # freight + origin + destination. Stored so ranking is a plain ORDER BY.
    total_amount: Mapped[Decimal] = mapped_column(Money)
    transit_time_days: Mapped[int] = mapped_column(Integer)
    quote_validity_date: Mapped[date] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    rfq: Mapped[Rfq] = relationship(back_populates="bids")
    supplier: Mapped[Supplier] = relationship()


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, native_enum=False, create_constraint=True, length=30))
    message: Mapped[str] = mapped_column(Text)
    # Only filled for AUCTION_EXTENDED, so the UI can show the change in local time.
    previous_close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    rfq: Mapped[Rfq] = relationship(back_populates="activity_logs")
