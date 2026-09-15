import asyncio
import logging
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import models  # noqa: F401 — side-effect import registers all ORM models with Base.metadata
from auth.dependencies import require_role
from auth.security import ACCESS_TOKEN_TYPE, JWTError, decode_token
from db import AsyncSessionLocal, Base, engine, settings
from models.error_log import ErrorLog
from routers import audit_log, auth, capacity, demand, error_log, leaves, physicians, sites, time_allocations

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


def _try_get_user_context(request: Request):
    """Best-effort decode of the bearer token, purely for error context — never raises."""
    try:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None, None
        payload = decode_token(auth_header.split(" ", 1)[1])
        if payload.get("type") != ACCESS_TOKEN_TYPE:
            return None, None
        return payload.get("sub"), payload.get("email")
    except JWTError:
        return None, None


# NOTE on ordering: this must be registered with add_middleware() BEFORE
# CORSMiddleware below. Starlette wraps middleware so the LAST one added ends
# up OUTERMOST; we need CORSMiddleware outermost (so it can attach headers to
# whatever comes back out) and this one INNERMOST (so it's the thing that
# actually catches the exception, right next to the router). A handler
# registered via @app.exception_handler(Exception) does NOT work for this —
# Starlette special-cases the base Exception/500 handler into its own
# ServerErrorMiddleware, which sits outside all user middleware including
# CORSMiddleware, so responses built there never get CORS headers attached.
# That was tried and empirically confirmed broken before landing on this.
@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    """
    Catches anything a route handler doesn't already turn into a clean
    response (HTTPException, RequestValidationError, etc. are handled by
    FastAPI before this ever sees them).

    Two things this fixes:
    1. An unhandled exception's default 500 response has no CORS headers
       (see the ordering note above), so the browser reports a bare
       "Failed to fetch" with no way to see what actually went wrong — this
       is exactly what happened with the life_no UNIQUE-constraint crash.
    2. It gives us one place to log every unexpected error — with an
       error_id a user can hand back to whoever's debugging it for them —
       to both the process log and a queryable error_log table.
    """
    try:
        return await call_next(request)
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        user_id, user_email = _try_get_user_context(request)

        logger.error(
            "Unhandled error [%s] %s %s (user=%s)",
            error_id, request.method, request.url.path, user_email or "anonymous",
            exc_info=exc,
        )

        try:
            async with AsyncSessionLocal() as db:
                db.add(ErrorLog(
                    error_id=error_id,
                    method=request.method,
                    path=request.url.path,
                    exception_type=type(exc).__name__,
                    message=str(exc)[:2000],
                    traceback=traceback.format_exc()[:8000],
                    user_id=uuid.UUID(user_id) if user_id else None,
                    user_email=user_email,
                ))
                await db.commit()
        except Exception:
            logger.exception("Failed to persist error_log row for [%s]", error_id)

        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error. Reference: {error_id}"},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All admin-only for this phase — no editor/viewer/provider enforcement yet.
_require_admin = [Depends(require_role("admin"))]

app.include_router(auth.router,       prefix="/api/auth",       tags=["auth"])
app.include_router(sites.router,      prefix="/api/sites",      tags=["sites"],      dependencies=_require_admin)
app.include_router(physicians.router, prefix="/api/physicians", tags=["physicians"], dependencies=_require_admin)
app.include_router(leaves.router,     prefix="/api/leaves",     tags=["leaves"],     dependencies=_require_admin)
app.include_router(demand.router,     prefix="/api/demand",     tags=["demand"],     dependencies=_require_admin)
app.include_router(capacity.router,   prefix="/api/capacity",   tags=["capacity"],   dependencies=_require_admin)
app.include_router(audit_log.router,  prefix="/api/audit-log",  tags=["audit-log"],  dependencies=_require_admin)
app.include_router(error_log.router,  prefix="/api/error-log",  tags=["error-log"],  dependencies=_require_admin)
app.include_router(time_allocations.router, prefix="/api",      tags=["time-allocations"], dependencies=_require_admin)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
