"""
User model for MongoDB with Pydantic validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic v2."""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_plain_validator_function(cls.validate)
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema, handler):
        field_schema.update(type="string")
        return field_schema


class UserBase(BaseModel):
    """Base user model with common fields."""
    email: EmailStr = Field(..., description="User email address")
    
    class Config:
        # Allow population by field name and alias
        populate_by_name = True
        # JSON encoders for custom types
        json_encoders = {ObjectId: str}


class UserCreate(UserBase):
    """User creation model."""
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")


class UserUpdate(BaseModel):
    """User update model."""
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    password: Optional[str] = Field(None, min_length=6, description="Updated password")


class UserInDB(UserBase):
    """User model as stored in database."""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    password_hash: str = Field(..., description="Hashed password")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="User creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    is_active: bool = Field(default=True, description="User active status")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class User(UserBase):
    """User model for API responses (without sensitive data)."""
    id: str = Field(..., description="User ID")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    is_active: bool = Field(..., description="User active status")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class UserLogin(BaseModel):
    """User login model."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    """User response model for authentication."""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    created_at: datetime = Field(..., description="User creation timestamp")
    is_active: bool = Field(..., description="User active status")
