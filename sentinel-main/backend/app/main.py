from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routes.billing import router as billing_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Sentinel",
    description="Real-time cloud cost anomaly detector",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(billing_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "sentinel"}
