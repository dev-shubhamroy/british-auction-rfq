import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.errors import BusinessRuleError, ConflictError, NotFoundError
from app.routes import rfqs, suppliers
from app.services.auction_service import close_expired_auctions

logger = logging.getLogger(__name__)


def close_auctions_once() -> None:
    with SessionLocal() as db:
        closed = close_expired_auctions(db)
        if closed:
            logger.info("Closed %d auction(s)", closed)


async def run_closer_loop() -> None:
    while True:
        try:
            # The DB call is blocking, so run it in a worker thread.
            await asyncio.to_thread(close_auctions_once)
        except Exception:
            logger.exception("Closing expired auctions failed; will retry")
        await asyncio.sleep(settings.closer_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    closer = asyncio.create_task(run_closer_loop())
    yield
    closer.cancel()


app = FastAPI(title="British Auction RFQ API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rfqs.router)
app.include_router(suppliers.router)


@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
def handle_conflict(request: Request, exc: ConflictError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(BusinessRuleError)
def handle_business_rule(request: Request, exc: BusinessRuleError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
