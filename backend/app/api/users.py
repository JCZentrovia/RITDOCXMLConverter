"""
User management API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query

from app.models import APIResponse, PaginationParams, PaginatedResponse
from app.models.user_management import (
    ExtendedUserResponse, UserProfileUpdate, PasswordChangeRequest,
    PasswordResetRequest, PasswordResetConfirm, AdminUserUpdate,
    UserListFilter, UserStatistics, UserActivityResponse, UserRole
)
from app.core.dependencies import get_current_user, require_admin_user
from app.services.user_management_service import user_management_service
from app.services.activity_service import activity_service
from app.models import UserInDB
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get(
    "/profile",
    response_model=APIResponse[ExtendedUserResponse],
    summary="Get user profile",
    description="Get current user's extended profile information"
)
async def get_user_profile(
    current_user: UserInDB = Depends(get_current_user)
):
    """Get current user's profile information."""
    try:
        user_profile = await user_management_service.get_user_by_id(str(current_user.id))
        
        if not user_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        return APIResponse[ExtendedUserResponse](
            success=True,
            message="User profile retrieved successfully",
            data=user_profile
        )
        
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )


@router.put(
    "/profile",
    response_model=APIResponse[ExtendedUserResponse],
    summary="Update user profile",
    description="Update current user's profile information"
)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    request: Request,
    current_user: UserInDB = Depends(get_current_user)
):
    """Update current user's profile information."""
    try:
        updated_user = await user_management_service.update_user_profile(
            user_id=str(current_user.id),
            profile_data=profile_data,
            request=request
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No changes were made to the profile"
            )
        
        return APIResponse[ExtendedUserResponse](
            success=True,
            message="Profile updated successfully",
            data=updated_user
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post(
    "/change-password",
    response_model=APIResponse[None],
    summary="Change password",
    description="Change current user's password"
)
async def change_password(
    password_data: PasswordChangeRequest,
    request: Request,
    current_user: UserInDB = Depends(get_current_user)
):
    """Change current user's password."""
    try:
        success = await user_management_service.change_password(
            user_id=str(current_user.id),
            password_data=password_data,
            request=request
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to change password"
            )
        
        return APIResponse[None](
            success=True,
            message="Password changed successfully",
            data=None
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.post(
    "/request-password-reset",
    response_model=APIResponse[dict],
    summary="Request password reset",
    description="Request password reset token (sent via email in production)"
)
async def request_password_reset(
    reset_request: PasswordResetRequest,
    request: Request
):
    """Request password reset token."""
    try:
        # Always return success to prevent email enumeration
        reset_token = await user_management_service.request_password_reset(
            email=reset_request.email,
            request=request
        )
        
        # In production, send token via email instead of returning it
        response_data = {
            "message": "If the email exists, a reset token has been sent"
        }
        
        # For development/testing, include the token
        if reset_token:
            response_data["reset_token"] = reset_token  # Remove this in production
        
        return APIResponse[dict](
            success=True,
            message="Password reset request processed",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error requesting password reset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        )


@router.post(
    "/reset-password",
    response_model=APIResponse[None],
    summary="Reset password",
    description="Reset password using reset token"
)
async def reset_password(
    reset_data: PasswordResetConfirm,
    request: Request
):
    """Reset password using reset token."""
    try:
        success = await user_management_service.reset_password(
            token=reset_data.token,
            new_password=reset_data.new_password,
            request=request
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        return APIResponse[None](
            success=True,
            message="Password reset successfully",
            data=None
        )
        
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )


@router.get(
    "/activities",
    response_model=APIResponse[List[UserActivityResponse]],
    summary="Get user activities",
    description="Get current user's activity history"
)
async def get_user_activities(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of activities"),
    skip: int = Query(0, ge=0, description="Number of activities to skip"),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get current user's activity history."""
    try:
        activities = await activity_service.get_user_activities(
            user_id=str(current_user.id),
            limit=limit,
            skip=skip
        )
        
        return APIResponse[List[UserActivityResponse]](
            success=True,
            message="User activities retrieved successfully",
            data=activities
        )
        
    except Exception as e:
        logger.error(f"Error getting user activities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user activities"
        )


# Admin endpoints
@router.get(
    "/admin/list",
    response_model=APIResponse[PaginatedResponse[ExtendedUserResponse]],
    summary="List users (Admin)",
    description="List all users with filtering (admin only)",
    tags=["Admin"]
)
async def list_users_admin(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    role: UserRole = Query(None, description="Filter by role"),
    is_active: bool = Query(None, description="Filter by active status"),
    is_verified: bool = Query(None, description="Filter by verification status"),
    search: str = Query(None, description="Search in email, name"),
    admin_user: UserInDB = Depends(require_admin_user)
):
    """List all users with filtering (admin only)."""
    try:
        # Build filters
        filters = UserListFilter(
            role=role,
            is_active=is_active,
            is_verified=is_verified,
            search=search
        )
        
        # Calculate pagination
        skip = (page - 1) * size
        
        # Get users
        users = await user_management_service.list_users(
            filters=filters,
            skip=skip,
            limit=size
        )
        
        # For simplicity, we'll return the users without total count
        # In production, you'd want to get the total count for proper pagination
        paginated_response = PaginatedResponse.create(
            items=users,
            total=len(users),  # This is not accurate, should be total count
            page=page,
            size=size
        )
        
        return APIResponse[PaginatedResponse[ExtendedUserResponse]](
            success=True,
            message="Users retrieved successfully",
            data=paginated_response
        )
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.put(
    "/admin/{user_id}",
    response_model=APIResponse[ExtendedUserResponse],
    summary="Update user (Admin)",
    description="Update any user's information (admin only)",
    tags=["Admin"]
)
async def update_user_admin(
    user_id: str,
    admin_data: AdminUserUpdate,
    request: Request,
    admin_user: UserInDB = Depends(require_admin_user)
):
    """Update any user's information (admin only)."""
    try:
        updated_user = await user_management_service.update_user_admin(
            user_id=user_id,
            admin_data=admin_data,
            admin_user_id=str(admin_user.id),
            request=request
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or no changes were made"
            )
        
        return APIResponse[ExtendedUserResponse](
            success=True,
            message="User updated successfully",
            data=updated_user
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.get(
    "/admin/statistics",
    response_model=APIResponse[UserStatistics],
    summary="Get user statistics (Admin)",
    description="Get comprehensive user statistics (admin only)",
    tags=["Admin"]
)
async def get_user_statistics(
    admin_user: UserInDB = Depends(require_admin_user)
):
    """Get comprehensive user statistics (admin only)."""
    try:
        statistics = await user_management_service.get_user_statistics()
        
        return APIResponse[UserStatistics](
            success=True,
            message="User statistics retrieved successfully",
            data=statistics
        )
        
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics"
        )


@router.get(
    "/admin/activities",
    response_model=APIResponse[List[UserActivityResponse]],
    summary="Get recent activities (Admin)",
    description="Get recent activities across all users (admin only)",
    tags=["Admin"]
)
async def get_recent_activities_admin(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of activities"),
    admin_user: UserInDB = Depends(require_admin_user)
):
    """Get recent activities across all users (admin only)."""
    try:
        activities = await activity_service.get_recent_activities(
            hours=hours,
            limit=limit
        )
        
        return APIResponse[List[UserActivityResponse]](
            success=True,
            message="Recent activities retrieved successfully",
            data=activities
        )
        
    except Exception as e:
        logger.error(f"Error getting recent activities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recent activities"
        )
