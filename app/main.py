"""
FastAPI application entry point.

Main application with:
- CORS configuration
- Structured logging
- Exception handlers
- Rate limiting
- Health checks
- API versioning

Run with: uvicorn app.main:app --reload

Version: 1.0.0
"""

import logging
import sys
import time
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import api_router
from app.core.config import get_settings


# Configure logging (deferred until startup to avoid import-time settings loading)
def setup_logging(settings_override=None):
    """
    Configure application logging.

    Args:
        settings_override: Optional Settings instance. If None, attempts to load settings.
                          Falls back to basic logging if settings unavailable.
    """
    try:
        if settings_override is None:
            from app.core.config import get_settings

            settings = get_settings()
        else:
            settings = settings_override
    except Exception:
        # Minimal fallback logger config if settings unavailable
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        return

    # Root logger configuration
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Add file handler if configured
    if settings.log_file:
        file_handler = logging.FileHandler(settings.log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)

    # Reduce noise from external libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# Note: Logging setup deferred to lifespan startup
# Do NOT call setup_logging() or get_settings() at module import time


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Load configuration, initialize logging, verify dependencies
    - Shutdown: Cleanup resources
    """
    # Load settings and configure logging
    settings = get_settings()
    setup_logging(settings)
    logger = logging.getLogger(__name__)

    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"API prefix: {settings.api_prefix}")
    logger.info(f"Rate limit: {settings.rate_limit_per_minute}/min")

    # Verify LLM configuration
    try:
        from app.core.llm_client import create_gemini_client

        _ = create_gemini_client()
        logger.info(f"LLM client initialized: {settings.gemini_model}")
    except Exception as e:
        logger.error(f"LLM client initialization failed: {type(e).__name__}")
        if settings.is_production:
            raise  # Fail fast in production
        logger.warning("Continuing without LLM client (non-production environment)")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutdown initiated")
    # Add cleanup logic here (close connections, etc.)
    logger.info("Application shutdown complete")


# Initialize FastAPI app
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="LLM-powered message analysis API for sentiment, emotion, and stress detection",
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.rate_limit_storage_uri)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# CORS middleware
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    # Note: CORS configuration logged in lifespan startup


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next: Callable):
    """
    Add unique request ID to each request for tracking.

    Request ID is available in logs and response headers.
    """
    request_id = f"{int(time.time() * 1000)}-{id(request)}"
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    """
    Log all HTTP requests with timing information.

    Logs: method, path, status code, processing time
    """
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate processing time
    process_time = (time.time() - start_time) * 1000

    # Log request (metadata only, no user data)
    request_logger = logging.getLogger(__name__)
    request_logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.2f}ms"
    )

    # Add timing header
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

    return response


# Exception handlers


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions with consistent JSON response format.
    Preserves structured detail if provided as dict.
    """
    # If detail is a dict with error info, use it directly
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    # Otherwise, wrap string detail in standard format
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "http_error",
            "message": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors with detailed error information.
    """
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(x) for x in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "validation_error",
            "message": "Request validation failed",
            "details": {"errors": errors},
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Handle rate limit exceeded errors.
    """
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "success": False,
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "details": {"limit": settings.rate_limit_per_minute, "window": "1 minute"},
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for unexpected exceptions.

    Logs full error details but returns safe error message to client.
    """
    exception_logger = logging.getLogger(__name__)
    exception_logger.error(
        f"Unhandled exception in {request.method} {request.url.path}: " f"{type(exc).__name__}",
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "internal_error",
            "message": "An unexpected error occurred. Please try again later.",
            "details": {"error_type": type(exc).__name__} if settings.debug else None,
        },
    )


# Include API routes
app.include_router(api_router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "docs": "/docs" if settings.debug else "disabled",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
