import os
import time
import logging
from collections import defaultdict
from typing import Dict, List

from fastapi import FastAPI, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db
from app.api.v1.api import api_router


logger = logging.getLogger("uvicorn.error")


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)


# ============================================================
# Uploads
# ============================================================

# Local:
#   ./uploads
#
# Vercel:
#   /tmp/uploads
#
# Note:
# Vercel filesystem is ephemeral. Persistent production uploads
# should eventually use object storage.

UPLOAD_ROOT = os.getenv(
    "UPLOAD_DIR",
    "/tmp/uploads"
    if os.getenv("VERCEL")
    else os.path.join(os.getcwd(), "uploads"),
)

os.makedirs(
    os.path.join(UPLOAD_ROOT, "products"),
    exist_ok=True,
)

app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_ROOT),
    name="uploads",
)


# ============================================================
# CORS Configuration
# ============================================================

# Start with configured origins from settings.
cors_origins = list(settings.BACKEND_CORS_ORIGINS or [])


# Add configured FRONTEND_URL if available.
if settings.FRONTEND_URL:
    frontend_url = settings.FRONTEND_URL.strip().rstrip("/")

    if frontend_url and frontend_url not in cors_origins:
        cors_origins.append(frontend_url)


# Production frontend applications.
# These are explicitly added so both the CMS and storefront
# can communicate with the same backend.
production_origins = [
    "https://e-cms-one.vercel.app",
    "https://e-public-puce.vercel.app",
]


for origin in production_origins:
    if origin not in cors_origins:
        cors_origins.append(origin)


# Local development origins.
local_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]


for origin in local_origins:
    if origin not in cors_origins:
        cors_origins.append(origin)


# Remove empty values and duplicate origins.
cors_origins = list(
    dict.fromkeys(
        origin.strip().rstrip("/")
        for origin in cors_origins
        if origin and origin.strip()
    )
)


logger.info(
    "Configured CORS origins: %s",
    cors_origins,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ============================================================
# Security Headers Middleware
# ============================================================

@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next,
):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = (
        "strict-origin-when-cross-origin"
    )

    return response


# ============================================================
# Authentication Rate Limiting
# ============================================================

# In-memory sliding window.
#
# Maximum:
#   30 authentication requests per minute per IP.
#
# IMPORTANT:
# OPTIONS requests are excluded because browser CORS
# preflight requests must not consume authentication limits.

_rate_limits: Dict[str, List[float]] = defaultdict(list)

AUTH_RATE_LIMIT_MAX = 30
AUTH_RATE_LIMIT_WINDOW = 60.0


@app.middleware("http")
async def auth_rate_limiter(
    request: Request,
    call_next,
):
    path = request.url.path

    # Never rate-limit CORS preflight requests.
    if request.method == "OPTIONS":
        return await call_next(request)

    is_auth_route = (
        path.endswith("/auth/login")
        or path.endswith("/auth/register")
    )

    if is_auth_route:
        client_ip = (
            request.client.host
            if request.client
            else "unknown"
        )

        now = time.time()

        timestamps = _rate_limits[client_ip]

        # Remove timestamps outside the rate-limit window.
        valid_timestamps = [
            timestamp
            for timestamp in timestamps
            if now - timestamp < AUTH_RATE_LIMIT_WINDOW
        ]

        _rate_limits[client_ip] = valid_timestamps

        if len(valid_timestamps) >= AUTH_RATE_LIMIT_MAX:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "message": (
                        "Too many requests. "
                        "Please slow down and try again shortly."
                    ),
                    "error_code": "RATE_LIMIT_EXCEEDED",
                },
            )

        _rate_limits[client_ip].append(now)

    return await call_next(request)


# ============================================================
# Error Handling
# ============================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "error_code": f"HTTP_{exc.status_code}",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    error_msgs = [
        f"{error['loc'][-1]}: {error['msg']}"
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": (
                "Validation error: "
                + ", ".join(error_msgs)
            ),
            "error_code": "VALIDATION_ERROR",
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.error(
        "Unhandled server error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": (
                "An unexpected server error occurred. "
                "Please try again later."
            ),
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


# ============================================================
# API Router
# ============================================================

app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
)


# ============================================================
# Health Check
# ============================================================

@app.get("/health", tags=["Health"])
@app.get(
    f"{settings.API_V1_STR}/health",
    tags=["Health"],
)
def health_check(
    db: Session = Depends(get_db),
):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"

    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return {
        "success": True,
        "status": (
            "healthy"
            if db_status == "connected"
            else "degraded"
        ),
        "database": db_status,
        "message": (
            "Production E-Commerce Platform API is running"
        ),
        "version": "1.0.0",
        "architecture": (
            "FastAPI + SQLAlchemy + PostgreSQL"
        ),
        "api_prefix": settings.API_V1_STR,
    }
