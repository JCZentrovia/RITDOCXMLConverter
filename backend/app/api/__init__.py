"""
API package initialization and router organization.
"""
from fastapi import APIRouter
from .v1 import api_router as v1_router

# Main API router that includes all versions
api_router = APIRouter()

# Include versioned routers
api_router.include_router(v1_router, prefix="/v1")

# Security and performance APIs removed

# Removed duplicate router inclusion to fix API docs

__all__ = ["api_router"]