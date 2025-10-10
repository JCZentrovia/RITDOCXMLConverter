"""
Manuscript model for MongoDB with Pydantic validation.
"""
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, validator
from bson import ObjectId
from .user import PyObjectId


class ManuscriptStatus(str, Enum):
    """Manuscript processing status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class ManuscriptBase(BaseModel):
    """Base manuscript model with common fields."""
    file_name: str = Field(..., min_length=1, max_length=255, description="Original file name")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class ManuscriptCreate(ManuscriptBase):
    """Manuscript creation model."""
    user_id: str = Field(..., description="ID of the user who uploaded the manuscript")
    pdf_s3_key: str = Field(..., description="S3 key for the PDF file")
    
    @validator('file_name')
    def validate_file_name(cls, v):
        if not v.lower().endswith('.pdf'):
            raise ValueError('File must be a PDF')
        return v


class ManuscriptUpdate(BaseModel):
    """Manuscript update model."""
    status: Optional[ManuscriptStatus] = Field(None, description="Updated manuscript status")
    docx_s3_key: Optional[str] = Field(None, description="S3 key for the converted Word document")
    xml_s3_key: Optional[str] = Field(None, description="S3 key for the converted XML document")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start timestamp")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    


class ManuscriptInDB(ManuscriptBase):
    """Manuscript model as stored in database."""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId = Field(..., description="ID of the user who uploaded the manuscript")
    status: ManuscriptStatus = Field(default=ManuscriptStatus.PENDING, description="Processing status")
    pdf_s3_key: str = Field(..., description="S3 key for the PDF file")
    docx_s3_key: Optional[str] = Field(None, description="S3 key for the converted Word document")
    xml_s3_key: Optional[str] =  Field(None, description="S3 key for the converted XML document")

    # Timestamps
    upload_date: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start timestamp")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")
    
    # Error handling
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    retry_count: int = Field(default=0, description="Number of processing retries")
    
    # File metadata
    file_size: Optional[int] = Field(None, description="File size in bytes")
    content_type: str = Field(default="application/pdf", description="MIME type of the file")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Manuscript(ManuscriptBase):
    """Manuscript model for API responses."""
    id: str = Field(..., description="Manuscript ID")
    user_id: str = Field(..., description="ID of the user who uploaded the manuscript")
    status: ManuscriptStatus = Field(..., description="Processing status")
    pdf_s3_key: str = Field(..., description="S3 key for the PDF file")
    docx_s3_key: Optional[str] = Field(None, description="S3 key for the converted Word document")
    
    # Timestamps
    upload_date: datetime = Field(..., description="Upload timestamp")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start timestamp")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")
    
    # Error handling
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    retry_count: int = Field(..., description="Number of processing retries")
    
    # File metadata
    file_size: Optional[int] = Field(None, description="File size in bytes")
    content_type: str = Field(..., description="MIME type of the file")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class ManuscriptResponse(BaseModel):
    """Simplified manuscript response model for API."""
    id: str = Field(..., description="Manuscript ID")
    file_name: str = Field(..., description="Original file name")
    status: ManuscriptStatus = Field(..., description="Processing status")
    upload_date: Optional[str] = Field(..., description="Upload timestamp (ISO format)")
    processing_completed_at: Optional[str] = Field(None, description="Processing completion timestamp (ISO format)")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class ManuscriptListResponse(BaseModel):
    """Response model for manuscript list."""
    manuscripts: list[ManuscriptResponse] = Field(..., description="List of manuscripts")
    total: int = Field(..., description="Total number of manuscripts")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class UploadUrlRequest(BaseModel):
    """Request model for generating upload URL."""
    file_name: str = Field(..., min_length=1, max_length=255, description="File name")
    file_size: Optional[int] = Field(None, gt=0, description="File size in bytes")
    content_type: str = Field(default="application/pdf", description="MIME type")
    
    @validator('file_name')
    def validate_file_name(cls, v):
        if not v.lower().endswith('.pdf'):
            raise ValueError('File must be a PDF')
        return v
    
    @validator('content_type')
    def validate_content_type(cls, v):
        if v != "application/pdf":
            raise ValueError('Content type must be application/pdf')
        return v


class UploadUrlResponse(BaseModel):
    """Response model for upload URL generation."""
    upload_url: str = Field(..., description="Pre-signed S3 upload URL")
    manuscript_id: str = Field(..., description="Generated manuscript ID")
    expires_in: int = Field(..., description="URL expiration time in seconds")


class DownloadUrlResponse(BaseModel):
    """Response model for download URL generation."""
    download_url: str = Field(..., description="Pre-signed S3 download URL")
    file_name: str = Field(..., description="File name")
    expires_in: int = Field(..., description="URL expiration time in seconds")
