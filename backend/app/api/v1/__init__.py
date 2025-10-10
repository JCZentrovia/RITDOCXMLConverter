"""
API v1 router organization.
"""
from fastapi import APIRouter
from ..auth import router as auth_router
from ..users import router as users_router
from ..manuscripts import router as manuscripts_router

# Create v1 API router
api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth_router, tags=["Authentication"])
api_router.include_router(users_router, tags=["User Management"])
api_router.include_router(manuscripts_router, tags=["Manuscript Management"])

# Health check endpoint for v1
@api_router.get(
    "/health",
    tags=["Health Check"],
    summary="API v1 Health Check",
    description="Check the health status of API v1 endpoints"
)
async def health_check_v1():
    """API v1 health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "api_version": "v1",
        "message": "Manuscript Processor API v1 is running"
    }

__all__ = ["api_router"]
