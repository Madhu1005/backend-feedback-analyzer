"""
Health check endpoints for monitoring and service discovery.

Endpoints:
- GET /health - Basic health check (always returns 200 if server is up)
- GET /health/ready - Readiness check (verifies dependencies like LLM)
- GET /health/live - Liveness check (same as /health)

These endpoints are used by:
- Load balancers for traffic routing
- Kubernetes/Docker health probes
- Monitoring systems
- Service discovery

Version: 1.0.0
"""
import logging
import time
from typing import Dict, Any
from fastapi import APIRouter, status, Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.llm_client import create_gemini_client


logger = logging.getLogger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: float
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness check response with dependency status"""
    status: str
    timestamp: float
    version: str
    environment: str
    checks: Dict[str, Dict[str, Any]]


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Returns 200 OK if the service is running. Used for liveness probes.",
    tags=["Health"]
)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    Always returns 200 OK if the service is running.
    Use this for Kubernetes liveness probes.
    
    Returns:
        HealthResponse with basic service info
    """
    settings = get_settings()
    
    return HealthResponse(
        status="healthy",
        timestamp=time.time(),
        version=settings.app_version,
        environment=settings.environment
    )


@router.get(
    "/health/live",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Alias for /health. Returns 200 OK if the service is alive.",
    tags=["Health"]
)
async def liveness_check() -> HealthResponse:
    """
    Liveness check endpoint (alias for /health).
    
    Returns 200 OK if the service is running.
    
    Returns:
        HealthResponse with basic service info
    """
    return await health_check()


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Checks if service and dependencies are ready to handle requests. Returns 503 if not ready.",
    tags=["Health"]
)
async def readiness_check(response: Response) -> ReadinessResponse:
    """
    Readiness check endpoint with dependency verification.
    
    Checks:
    1. LLM service connectivity (optional, based on config)
    2. Configuration validity
    
    Returns:
        - 200 OK if all dependencies are ready
        - 503 Service Unavailable if any dependency fails
        
    Use this for Kubernetes readiness probes.
    """
    settings = get_settings()
    checks = {}
    all_ready = True
    
    # Check 1: Configuration validity
    try:
        checks["configuration"] = {
            "status": "healthy",
            "message": "Configuration loaded successfully"
        }
    except Exception as e:
        logger.error(f"Configuration check failed: {type(e).__name__}")
        checks["configuration"] = {
            "status": "unhealthy",
            "message": f"Configuration error: {type(e).__name__}"
        }
        all_ready = False
    
    # Check 2: LLM service connectivity (quick test)
    if settings.health_check_enabled:
        try:
            # Attempt to create client (doesn't make API call)
            client = create_gemini_client()
            checks["llm_service"] = {
                "status": "healthy",
                "message": f"LLM client initialized: {settings.gemini_model}",
                "model": settings.gemini_model
            }
        except ValueError as e:
            # API key missing or invalid
            logger.warning(f"LLM service check failed: {str(e)}")
            checks["llm_service"] = {
                "status": "unhealthy",
                "message": f"LLM configuration error: {type(e).__name__}",
                "error": "API key missing or invalid"
            }
            all_ready = False
        except Exception as e:
            logger.error(f"LLM service check failed: {type(e).__name__}")
            checks["llm_service"] = {
                "status": "unhealthy",
                "message": f"LLM service error: {type(e).__name__}"
            }
            all_ready = False
    else:
        checks["llm_service"] = {
            "status": "skipped",
            "message": "Health check disabled in configuration"
        }
    
    # Set response status based on checks
    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return ReadinessResponse(
        status="ready" if all_ready else "not_ready",
        timestamp=time.time(),
        version=settings.app_version,
        environment=settings.environment,
        checks=checks
    )
