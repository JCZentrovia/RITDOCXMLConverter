"""
FastAPI dependencies for authentication and authorization.
"""
from typing import Optional, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.core.security import verify_token
from app.models import UserInDB
from app.services.user_service import user_service
import logging

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInDB:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials from request header
        
    Returns:
        UserInDB: Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify and decode JWT token
        payload = verify_token(credentials.credentials)
        if payload is None:
            logger.warning("Invalid JWT token provided")
            raise credentials_exception
        
        # Extract user ID from token
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("JWT token missing user ID (sub claim)")
            raise credentials_exception
        
        # Get user from database
        user = await user_service.get_user_by_id(user_id)
        if user is None:
            logger.warning(f"User not found for ID: {user_id}")
            raise credentials_exception
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user account"
            )
        
        return user
        
    except JWTError as e:
        logger.warning(f"JWT error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Error in get_current_user: {e}")
        raise credentials_exception


async def get_current_active_user(
    current_user: UserInDB = Depends(get_current_user)
) -> UserInDB:
    """
    Get current active user (additional check for user status).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        UserInDB: Current active user
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserInDB]:
    """
    Get current user if token is provided, otherwise return None.
    Useful for endpoints that work for both authenticated and anonymous users.
    
    Args:
        credentials: Optional HTTP Bearer credentials
        
    Returns:
        Optional[UserInDB]: Current user if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        # Verify and decode JWT token
        payload = verify_token(credentials.credentials)
        if payload is None:
            return None
        
        # Extract user ID from token
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        # Get user from database
        user = await user_service.get_user_by_id(user_id)
        if user is None or not user.is_active:
            return None
        
        return user
        
    except Exception as e:
        logger.debug(f"Optional auth failed: {e}")
        return None


def require_admin_user(
    current_user: UserInDB = Depends(get_current_active_user)
) -> UserInDB:
    """
    Require admin user access (placeholder for future admin functionality).
    
    Args:
        current_user: Current active user
        
    Returns:
        UserInDB: Current user if admin
        
    Raises:
        HTTPException: If user is not admin
    """
    # For now, all active users are considered admins
    # In the future, you can add an 'is_admin' field to the User model
    # and check: if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    return current_user


class RateLimitDependency:
    """Rate limiting dependency (placeholder for future implementation)."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
    
    async def __call__(self, request: Optional[Any] = None) -> None:
        """
        Rate limiting check (placeholder).
        
        In a production environment, you would implement actual rate limiting
        using Redis or in-memory storage to track request counts per user/IP.
        """
        # Placeholder - implement actual rate limiting logic here
        pass


# Common rate limit instances
rate_limit_auth = RateLimitDependency(requests_per_minute=10)  # Stricter for auth endpoints
rate_limit_api = RateLimitDependency(requests_per_minute=60)   # Standard for API endpoints
