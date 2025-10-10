"""
Extended user management models.
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, validator

from .user import PyObjectId


class UserRole(str, Enum):
    """User role enumeration."""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class ActivityType(str, Enum):
    """User activity type enumeration."""
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    PROFILE_UPDATE = "profile_update"
    ACCOUNT_DEACTIVATE = "account_deactivate"
    ACCOUNT_ACTIVATE = "account_activate"
    MANUSCRIPT_UPLOAD = "manuscript_upload"
    MANUSCRIPT_DOWNLOAD = "manuscript_download"


class UserProfileUpdate(BaseModel):
    """User profile update model."""
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    first_name: Optional[str] = Field(None, min_length=1, max_length=50, description="First name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=50, description="Last name")
    
    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        if v is not None and v.strip() != v:
            raise ValueError('Name cannot have leading or trailing whitespace')
        return v


class PasswordChangeRequest(BaseModel):
    """Password change request model."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class PasswordResetRequest(BaseModel):
    """Password reset request model."""
    email: EmailStr = Field(..., description="Email address for password reset")


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation model."""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class UserActivityLog(BaseModel):
    """User activity log model."""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId = Field(..., description="User ID")
    activity_type: ActivityType = Field(..., description="Type of activity")
    description: str = Field(..., description="Activity description")
    ip_address: Optional[str] = Field(None, description="User IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    metadata: Optional[dict] = Field(None, description="Additional activity metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Activity timestamp")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}


class UserActivityResponse(BaseModel):
    """User activity response model."""
    id: str = Field(..., description="Activity ID")
    activity_type: ActivityType = Field(..., description="Type of activity")
    description: str = Field(..., description="Activity description")
    ip_address: Optional[str] = Field(None, description="User IP address")
    timestamp: datetime = Field(..., description="Activity timestamp")


class ExtendedUserInDB(BaseModel):
    """Extended user model with additional fields."""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    email: EmailStr = Field(..., description="User email address")
    password_hash: str = Field(..., description="Hashed password")
    
    # Profile information
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    
    # Account status
    is_active: bool = Field(default=True, description="User active status")
    is_verified: bool = Field(default=False, description="Email verification status")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="User creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    
    # Password reset
    reset_token: Optional[str] = Field(None, description="Password reset token")
    reset_token_expires: Optional[datetime] = Field(None, description="Reset token expiration")
    
    # Account statistics
    login_count: int = Field(default=0, description="Total login count")
    manuscript_count: int = Field(default=0, description="Total manuscripts uploaded")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}


class ExtendedUserResponse(BaseModel):
    """Extended user response model."""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    is_active: bool = Field(..., description="User active status")
    is_verified: bool = Field(..., description="Email verification status")
    role: UserRole = Field(..., description="User role")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    login_count: int = Field(..., description="Total login count")
    manuscript_count: int = Field(..., description="Total manuscripts uploaded")
    
    @property
    def full_name(self) -> Optional[str]:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return None


class AdminUserUpdate(BaseModel):
    """Admin user update model."""
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    first_name: Optional[str] = Field(None, min_length=1, max_length=50, description="First name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=50, description="Last name")
    is_active: Optional[bool] = Field(None, description="User active status")
    is_verified: Optional[bool] = Field(None, description="Email verification status")
    role: Optional[UserRole] = Field(None, description="User role")


class UserListFilter(BaseModel):
    """User list filtering parameters."""
    role: Optional[UserRole] = Field(None, description="Filter by user role")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_verified: Optional[bool] = Field(None, description="Filter by verification status")
    search: Optional[str] = Field(None, min_length=1, description="Search in email, first name, last name")
    created_after: Optional[datetime] = Field(None, description="Filter users created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter users created before this date")


class UserStatistics(BaseModel):
    """User statistics model."""
    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    verified_users: int = Field(..., description="Number of verified users")
    admin_users: int = Field(..., description="Number of admin users")
    users_today: int = Field(..., description="Users registered today")
    users_this_week: int = Field(..., description="Users registered this week")
    users_this_month: int = Field(..., description="Users registered this month")
    total_logins: int = Field(..., description="Total login count across all users")
    total_manuscripts: int = Field(..., description="Total manuscripts uploaded")
