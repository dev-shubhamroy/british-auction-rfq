from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# Make every connection use UTC so timestamps come back as UTC regardless of
# the database server's local timezone.
engine = create_engine(settings.database_url, connect_args={"options": "-c timezone=utc"})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
