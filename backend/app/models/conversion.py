"""
Pydantic models for PDF to Word conversion operations.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field

from app.models.user import PyObjectId

class ConversionStatus(str, Enum):
    """Conversion status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ConversionQuality(str, Enum):
    """Conversion quality enumeration."""
    STANDARD = "standard"
    HIGH = "high"

class ConversionTaskCreate(BaseModel):
    """Model for creating a new conversion task."""
    manuscript_id: str = Field(..., description="ID of the manuscript to convert")
    user_id: str = Field(..., description="ID of the user requesting conversion")
    quality: ConversionQuality = Field(ConversionQuality.STANDARD, description="Conversion quality")
    include_metadata: bool = Field(True, description="Whether to include document metadata")
    priority: int = Field(1, description="Conversion priority (1-10, higher is more urgent)")

class ConversionTaskUpdate(BaseModel):
    """Model for updating a conversion task."""
    status: Optional[ConversionStatus] = Field(None, description="Conversion status")
    progress_percentage: Optional[int] = Field(None, description="Conversion progress (0-100)")
    error_message: Optional[str] = Field(None, description="Error message if conversion failed")
    conversion_metadata: Optional[Dict[str, Any]] = Field(None, description="Conversion metadata and statistics")
    docx_s3_key: Optional[str] = Field(None, description="S3 key of the converted DOCX file")
    processing_started_at: Optional[datetime] = Field(None, description="When processing started")
    processing_completed_at: Optional[datetime] = Field(None, description="When processing completed")
    retry_count: Optional[int] = Field(None, description="Number of retry attempts")

class ConversionTaskInDB(BaseModel):
    """Model for conversion task stored in database."""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id", description="Conversion task ID")
    manuscript_id: str = Field(..., description="ID of the manuscript to convert")
    user_id: str = Field(..., description="ID of the user requesting conversion")
    
    # Conversion settings
    quality: ConversionQuality = Field(..., description="Conversion quality")
    include_metadata: bool = Field(..., description="Whether to include document metadata")
    priority: int = Field(..., description="Conversion priority")
    
    # Status and progress
    status: ConversionStatus = Field(..., description="Current conversion status")
    progress_percentage: int = Field(0, description="Conversion progress (0-100)")
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Task creation time")
    processing_started_at: Optional[datetime] = Field(None, description="When processing started")
    processing_completed_at: Optional[datetime] = Field(None, description="When processing completed")
    
    # Results
    docx_s3_key: Optional[str] = Field(None, description="S3 key of the converted DOCX file")
    error_message: Optional[str] = Field(None, description="Error message if conversion failed")
    conversion_metadata: Optional[Dict[str, Any]] = Field(None, description="Conversion metadata and statistics")
    
    # Retry handling
    retry_count: int = Field(0, description="Number of retry attempts")
    max_retries: int = Field(3, description="Maximum number of retry attempts")
    
    # Scheduling
    scheduled_for: Optional[datetime] = Field(None, description="When the task is scheduled to run")
    locked_by: Optional[str] = Field(None, description="Worker ID that locked this task")
    locked_at: Optional[datetime] = Field(None, description="When the task was locked")
    lock_expires_at: Optional[datetime] = Field(None, description="When the lock expires")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
        json_schema_extra = {
            "example": {
                "manuscript_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "quality": "standard",
                "include_metadata": True,
                "priority": 1,
                "status": "pending",
                "progress_percentage": 0,
                "created_at": "2024-01-01T12:00:00Z",
                "retry_count": 0,
                "max_retries": 3
            }
        }

class ConversionTaskResponse(BaseModel):
    """Model for conversion task API response."""
    id: str = Field(..., description="Conversion task ID")
    manuscript_id: str = Field(..., description="ID of the manuscript being converted")
    status: ConversionStatus = Field(..., description="Current conversion status")
    progress_percentage: int = Field(..., description="Conversion progress (0-100)")
    quality: ConversionQuality = Field(..., description="Conversion quality")
    created_at: datetime = Field(..., description="Task creation time")
    processing_started_at: Optional[datetime] = Field(None, description="When processing started")
    processing_completed_at: Optional[datetime] = Field(None, description="When processing completed")
    error_message: Optional[str] = Field(None, description="Error message if conversion failed")
    retry_count: int = Field(..., description="Number of retry attempts")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")

class ConversionTaskListResponse(BaseModel):
    """Model for paginated conversion task list response."""
    tasks: List[ConversionTaskResponse] = Field(..., description="List of conversion tasks")
    total: int = Field(..., description="Total number of tasks")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")

class ConversionStatistics(BaseModel):
    """Model for conversion statistics."""
    total_conversions: int = Field(..., description="Total number of conversions")
    status_counts: Dict[str, int] = Field(..., description="Count by status")
    pending: int = Field(..., description="Number of pending conversions")
    processing: int = Field(..., description="Number of processing conversions")
    completed: int = Field(..., description="Number of completed conversions")
    failed: int = Field(..., description="Number of failed conversions")
    cancelled: int = Field(..., description="Number of cancelled conversions")
    
    # Performance metrics
    average_processing_time_seconds: float = Field(0.0, description="Average processing time")
    total_processing_time_seconds: float = Field(0.0, description="Total processing time")
    success_rate_percentage: float = Field(0.0, description="Success rate percentage")
    
    # Quality distribution
    quality_distribution: Dict[str, int] = Field(default_factory=dict, description="Distribution by quality")
    
    # Recent activity
    conversions_last_24h: int = Field(0, description="Conversions in last 24 hours")
    conversions_last_7d: int = Field(0, description="Conversions in last 7 days")

class ConversionRequest(BaseModel):
    """Model for requesting a new conversion."""
    manuscript_id: str = Field(..., description="ID of the manuscript to convert")
    quality: ConversionQuality = Field(ConversionQuality.STANDARD, description="Conversion quality")
    include_metadata: bool = Field(True, description="Whether to include document metadata")
    priority: int = Field(1, description="Conversion priority (1-10)")

class ConversionProgress(BaseModel):
    """Model for conversion progress updates."""
    task_id: str = Field(..., description="Conversion task ID")
    status: ConversionStatus = Field(..., description="Current status")
    progress_percentage: int = Field(..., description="Progress percentage (0-100)")
    message: str = Field("", description="Progress message")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    current_step: str = Field("", description="Current processing step")

class ConversionResult(BaseModel):
    """Model for conversion completion result."""
    task_id: str = Field(..., description="Conversion task ID")
    manuscript_id: str = Field(..., description="Original manuscript ID")
    status: ConversionStatus = Field(..., description="Final conversion status")
    docx_s3_key: Optional[str] = Field(None, description="S3 key of converted DOCX file")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Performance metrics
    processing_time_seconds: float = Field(..., description="Total processing time")
    input_file_size_mb: float = Field(..., description="Input file size in MB")
    output_file_size_mb: Optional[float] = Field(None, description="Output file size in MB")
    
    # Conversion details
    quality: ConversionQuality = Field(..., description="Conversion quality used")
    pages_processed: int = Field(..., description="Number of pages processed")
    conversion_metadata: Optional[Dict[str, Any]] = Field(None, description="Detailed conversion metadata")

class WorkerStatus(BaseModel):
    """Model for conversion worker status."""
    worker_id: str = Field(..., description="Unique worker identifier")
    status: str = Field(..., description="Worker status (active, idle, error)")
    current_task_id: Optional[str] = Field(None, description="Currently processing task ID")
    tasks_processed: int = Field(0, description="Total tasks processed by this worker")
    last_heartbeat: datetime = Field(..., description="Last worker heartbeat")
    started_at: datetime = Field(..., description="When the worker started")
    
    # Performance metrics
    average_task_time_seconds: float = Field(0.0, description="Average task processing time")
    success_rate_percentage: float = Field(0.0, description="Task success rate")
    
    # Resource usage
    cpu_usage_percentage: Optional[float] = Field(None, description="CPU usage percentage")
    memory_usage_mb: Optional[float] = Field(None, description="Memory usage in MB")

class ConversionQueue(BaseModel):
    """Model for conversion queue status."""
    total_pending: int = Field(..., description="Total pending tasks")
    total_processing: int = Field(..., description="Total processing tasks")
    queue_length: int = Field(..., description="Current queue length")
    estimated_wait_time_seconds: float = Field(..., description="Estimated wait time for new tasks")
    active_workers: int = Field(..., description="Number of active workers")
    
    # Priority distribution
    priority_distribution: Dict[int, int] = Field(default_factory=dict, description="Tasks by priority")
    
    # Queue health
    oldest_pending_task_age_seconds: float = Field(0.0, description="Age of oldest pending task")
    average_queue_time_seconds: float = Field(0.0, description="Average time tasks spend in queue")
