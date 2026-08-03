import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models  # noqa: F401 — side-effect import registers all ORM models with Base.metadata
from db import Base, engine, settings
from routers import capacity, demand, leaves, physicians, sites

logger = logging.getLogger("uvicorn.error")

_MAX_STARTUP_ATTEMPTS = 10
_STARTUP_BACKOFF_BASE = 1.5  # seconds; doubles each retry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Attempt to connect and run create_all with exponential backoff.
    # This handles the window between pg_isready passing and the DB
    # accepting connections over the Docker network (DNS propagation,
    # TCP stack init, etc.).
    for attempt in range(1, _MAX_STARTUP_ATTEMPTS + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database connection established.")
            break
        except Exception as exc:
            if attempt == _MAX_STARTUP_ATTEMPTS:
                logger.error("Could not connect to the database after %d attempts.", attempt)
                raise
            wait = _STARTUP_BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "DB not ready (attempt %d/%d): %s. Retrying in %.1fs…",
                attempt, _MAX_STARTUP_ATTEMPTS, exc, wait,
            )
            await asyncio.sleep(wait)

    yield
    await engine.dispose()


app = FastAPI(
    title="ED Capacity Planner API",
    description="Backend for the Mount Sinai Emergency Medicine capacity planning tool.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sites.router,      prefix="/api/sites",      tags=["sites"])
app.include_router(physicians.router, prefix="/api/physicians", tags=["physicians"])
app.include_router(leaves.router,     prefix="/api/leaves",     tags=["leaves"])
app.include_router(demand.router,     prefix="/api/demand",     tags=["demand"])
app.include_router(capacity.router,   prefix="/api/capacity",   tags=["capacity"])


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
