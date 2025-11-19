"""
API router aggregation.

Combines all API routers and applies versioning prefix.

Version: 1.0.0
"""
from fastapi import APIRouter

from app.api import analyze, health


# Create main API router with versioning
api_router = APIRouter()

# Include health endpoints (no prefix for standard /health path)
api_router.include_router(
    health.router,
    prefix="",
    tags=["Health"]
)

# Include analysis endpoints with /api/v1 prefix
api_router.include_router(
    analyze.router,
    prefix="/api/v1",
    tags=["Analysis"]
)
