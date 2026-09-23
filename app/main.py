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

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Uploads:
# - Local development: ./uploads
# - Vercel: /tmp/uploads (ephemeral; use object storage for persistent media)
UPLOAD_ROOT = os.getenv(
    "UPLOAD_DIR",
    "/tmp/uploads" if os.getenv("VERCEL") else os.path.join(os.getcwd(), "uploads"),
)
os.makedirs(os.path.join(UPLOAD_ROOT, "products"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")

# 1. Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# 2. Rate Limiting for Sensitive Authentication Endpoints
# In-memory sliding window: max 30 requests per minute per IP for auth routes
_rate_limits: Dict[str, List[float]] = defaultdict(list)
AUTH_RATE_LIMIT_MAX = 30
AUTH_RATE_LIMIT_WINDOW = 60.0

@app.middleware("http")
async def auth_rate_limiter(request: Request, call_next):
    path = request.url.path
    if path.endswith("/auth/login") or path.endswith("/auth/register"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        timestamps = _rate_limits[client_ip]
        # Purge entries older than window
        _rate_limits[client_ip] = [t for t in timestamps if now - t < AUTH_RATE_LIMIT_WINDOW]
        if len(_rate_limits[client_ip]) >= AUTH_RATE_LIMIT_MAX:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "message": "Too many requests. Please slow down and try again shortly.",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }
            )
        _rate_limits[client_ip].append(now)

    return await call_next(request)

# CORS Setup
# Keep local development origins and optionally add the deployed frontend URL
# through the FRONTEND_URL environment variable. Do not use wildcard origins
# with credentials.
cors_origins = list(settings.BACKEND_CORS_ORIGINS)
if settings.FRONTEND_URL:
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    if frontend_url and frontend_url not in cors_origins:
        cors_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Consistent Error Handling
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "error_code": f"HTTP_{exc.status_code}"
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_msgs = [f"{e['loc'][-1]}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error: " + ", ".join(error_msgs),
            "error_code": "VALIDATION_ERROR"
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An unexpected server error occurred. Please try again later.",
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    return {
        "success": True,
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "message": "Production E-Commerce Platform API is running",
        "version": "1.0.0",
        "architecture": "FastAPI + SQLAlchemy + PostgreSQL",
        "api_prefix": settings.API_V1_STR
    }
