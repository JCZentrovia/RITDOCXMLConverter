"""Data models."""

# User models
from .user import (
    User,
    UserCreate,
    UserUpdate,
    UserInDB,
    UserLogin,
    UserResponse,
    PyObjectId
)

# Manuscript models
from .manuscript import (
    Manuscript,
    ManuscriptCreate,
    ManuscriptUpdate,
    ManuscriptInDB,
    ManuscriptResponse,
    ManuscriptListResponse,
    ManuscriptStatus,
    UploadUrlRequest,
    UploadUrlResponse,
    DownloadUrlResponse
)

# Common models
from .common import (
    APIResponse,
    ErrorResponse,
    PaginationParams,
    PaginatedResponse,
    HealthCheckResponse,
    TokenResponse
)

# User management models
from .user_management import (
    UserRole,
    ActivityType,
    UserProfileUpdate,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    UserActivityLog,
    UserActivityResponse,
    ExtendedUserInDB,
    ExtendedUserResponse,
    AdminUserUpdate,
    UserListFilter,
    UserStatistics
)

__all__ = [
    # User models
    "User",
    "UserCreate", 
    "UserUpdate",
    "UserInDB",
    "UserLogin",
    "UserResponse",
    "PyObjectId",
    
    # Manuscript models
    "Manuscript",
    "ManuscriptCreate",
    "ManuscriptUpdate", 
    "ManuscriptInDB",
    "ManuscriptResponse",
    "ManuscriptListResponse",
    "ManuscriptStatus",
    "UploadUrlRequest",
    "UploadUrlResponse",
    "DownloadUrlResponse",
    
    # Common models
    "APIResponse",
    "ErrorResponse",
    "PaginationParams",
    "PaginatedResponse",
    "HealthCheckResponse",
    "TokenResponse",
    
    # User management models
    "UserRole",
    "ActivityType",
    "UserProfileUpdate",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "UserActivityLog",
    "UserActivityResponse",
    "ExtendedUserInDB",
    "ExtendedUserResponse",
    "AdminUserUpdate",
    "UserListFilter",
    "UserStatistics"
]
