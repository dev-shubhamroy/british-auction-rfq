"""Create demo suppliers and one live auction. Run with: python -m app.seed"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app import clock
from app.database import Base, SessionLocal, engine
from app.models import Rfq, Supplier, TriggerType
from app.schemas import BidCreate, RfqCreate
from app.services.auction_service import submit_bid
from app.services.rfq_service import create_rfq

SUPPLIERS = [
    "Atlas Freight",
    "BlueWave Logistics",
    "Cargo Express",
    "Delta Shipping",
    "Everest Forwarders",
]


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for name in SUPPLIERS:
            if not db.scalar(select(Supplier).where(Supplier.name == name)):
                db.add(Supplier(name=name))
        db.commit()

        if db.scalar(select(Rfq.id).limit(1)):
            print("RFQs already exist; only suppliers were seeded.")
            return

        now = clock.utc_now().replace(second=0, microsecond=0)
        rfq = create_rfq(db, RfqCreate(
            reference_id="RFQ-DEMO-001",
            name="Mumbai to Rotterdam - 2x40ft containers",
            pickup_date=date.today() + timedelta(days=14),
            bid_start_time=now - timedelta(minutes=30),
            bid_close_time=now + timedelta(minutes=20),
            forced_close_time=now + timedelta(minutes=45),
            trigger_window_minutes=10,
            extension_minutes=5,
            trigger_type=TriggerType.L1_CHANGE,
        ))

        suppliers = {s.name: s for s in db.scalars(select(Supplier))}
        validity = date.today() + timedelta(days=30)
        for supplier_name, carrier, freight in [
            ("Atlas Freight", "Maersk", "52000"),
            ("BlueWave Logistics", "MSC", "49500"),
        ]:
            submit_bid(db, rfq.id, BidCreate(
                supplier_id=suppliers[supplier_name].id,
                carrier_name=carrier,
                freight_charges=Decimal(freight),
                origin_charges=Decimal("3000"),
                destination_charges=Decimal("2500"),
                transit_time_days=21,
                quote_validity_date=validity,
            ))
        print(f"Seeded {len(SUPPLIERS)} suppliers and demo auction {rfq.reference_id}.")


if __name__ == "__main__":
    seed()
