"""
Authentication API endpoints.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.models import (
    UserLogin, 
    UserCreate, 
    UserResponse, 
    TokenResponse, 
    APIResponse,
    ErrorResponse
)
from app.core.security import create_access_token
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.services.user_service import user_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=APIResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email and password"
)
async def register(user_data: UserCreate):
    """
    Register a new user account.
    
    - **email**: Valid email address (will be used for login)
    - **password**: Password (minimum 6 characters)
    
    Returns the created user information (without password).
    """
    try:
        # Create user in database
        user_in_db = await user_service.create_user(user_data)
        
        # Convert to response model
        user_response = UserResponse(
            id=str(user_in_db.id),
            email=user_in_db.email,
            created_at=user_in_db.created_at,
            is_active=user_in_db.is_active
        )
        
        logger.info(f"User registered successfully: {user_data.email}")
        
        return APIResponse[UserResponse](
            success=True,
            message="User registered successfully. Your account is pending approval and will be activated manually.",
            data=user_response
        )
        
    except ValueError as e:
        logger.warning(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user and return JWT access token"
)
async def login(user_credentials: UserLogin):
    """
    Authenticate user and return access token.
    
    - **email**: User email address
    - **password**: User password
    
    Returns JWT access token for authenticated requests.
    """
    try:
        # Authenticate user
        user = await user_service.authenticate_user(
            user_credentials.email, 
            user_credentials.password
        )
        
        if not user:
            # Check if user exists but is inactive
            existing_user = await user_service.get_user_by_email(user_credentials.email)
            if existing_user and not existing_user.is_active:
                logger.warning(f"Login failed for email: {user_credentials.email} - Account not activated")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Your account is pending approval. Please contact an administrator to activate your account.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            logger.warning(f"Login failed for email: {user_credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email},
            expires_delta=access_token_expires
        )
        
        logger.info(f"User logged in successfully: {user.email}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60  # Convert to seconds
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post(
    "/logout",
    response_model=APIResponse[None],
    summary="User logout",
    description="Logout user (client should discard the token)"
)
async def logout(
    current_user = Depends(get_current_user)
):
    """
    Logout current user.
    
    Note: Since JWT tokens are stateless, the actual logout is handled
    on the client side by discarding the token. This endpoint serves
    as a confirmation and for logging purposes.
    
    In a production environment, you might want to implement a token
    blacklist to prevent reuse of tokens before they expire.
    """
    logger.info(f"User logged out: {current_user.email}")
    
    return APIResponse[None](
        success=True,
        message="Logged out successfully",
        data=None
    )


@router.get(
    "/me",
    response_model=APIResponse[UserResponse],
    summary="Get current user",
    description="Get current authenticated user information"
)
async def get_current_user_info(
    current_user = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    
    Returns user profile information for the currently authenticated user.
    """
    user_response = UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        created_at=current_user.created_at,
        is_active=current_user.is_active
    )
    
    return APIResponse[UserResponse](
        success=True,
        message="User information retrieved successfully",
        data=user_response
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Refresh JWT access token for authenticated user"
)
async def refresh_token(
    current_user = Depends(get_current_user)
):
    """
    Refresh access token for current user.
    
    Generates a new JWT token with extended expiration time.
    The old token will remain valid until it expires naturally.
    """
    try:
        # Create new access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(current_user.id), "email": current_user.email},
            expires_delta=access_token_expires
        )
        
        logger.info(f"Token refreshed for user: {current_user.email}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        )
        
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get(
    "/validate",
    response_model=APIResponse[dict],
    summary="Validate token",
    description="Validate current JWT token"
)
async def validate_token(
    current_user = Depends(get_current_user)
):
    """
    Validate current JWT token.
    
    Returns token validation status and user information.
    Useful for client-side token validation.
    """
    return APIResponse[dict](
        success=True,
        message="Token is valid",
        data={
            "user_id": str(current_user.id),
            "email": current_user.email,
            "is_active": current_user.is_active
        }
    )
