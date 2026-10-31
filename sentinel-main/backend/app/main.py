import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import configure_logging, get_settings
from app.database import Base, SessionLocal, engine
from app.routes.anomaly import router as anomaly_router
from app.routes.billing import router as billing_router

configure_logging()
logger = logging.getLogger("sentinel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("sentinel started (log_level=%s)", get_settings().log_level)
    yield


app = FastAPI(
    title="Sentinel",
    description="Cloud cost anomaly detector",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(billing_router)
app.include_router(anomaly_router)


@app.get("/health")
def health():
    """Liveness + readiness probe. Reports database reachability.

    Returns 200 when the database responds to ``SELECT 1`` and 503 when it is
    unreachable, so orchestrators can route traffic away from a degraded pod.
    """
    status = {"status": "ok", "service": "sentinel"}
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        status["database"] = "ok"
    except Exception as exc:  # pragma: no cover - exercised when DB is down
        status["status"] = "degraded"
        status["database"] = "error"
        status["detail"] = str(exc)
        return JSONResponse(status_code=503, content=status)
    return status
