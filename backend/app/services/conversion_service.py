"""
Conversion Service for managing PDF to XML conversion tasks.

This service handles the creation, tracking, and management of conversion tasks,
including queue management, progress tracking, and result handling.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging_config import LoggingContext, conversion_logger, performance_logger
from app.core.error_handling import (
    DatabaseError, BusinessLogicError, ErrorContext,
    error_handler, retry_manager, rollback_manager
)
# Monitoring imports removed

from app.core.collections import Collections
from app.core.database import get_database
from app.models.conversion import (
    ConversionTaskCreate, ConversionTaskUpdate, ConversionTaskInDB,
    ConversionTaskResponse, ConversionTaskListResponse, ConversionStatistics,
    ConversionStatus, ConversionQuality, ConversionProgress, ConversionResult
)
from app.models.manuscript import ManuscriptInDB, ManuscriptStatus, ManuscriptUpdate
from app.services.pdf_conversion_service import pdf_conversion_service
from app.core.error_handling import ConversionError
from app.services.docbook_conversion_service import docbook_conversion_service
from app.services.manuscript_service import manuscript_service

logger = logging.getLogger(__name__)

class ConversionService:
    """Service for managing PDF to XML conversion tasks."""

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        self.db = db
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        logger.info(f"Conversion service initialized with worker ID: {self.worker_id}")

    def _get_collection(self):
        """Lazily get the conversion tasks collection."""
        if self.db is None:
            self.db = get_database()
        return self.db[Collections.CONVERSION_TASKS]

    async def create_conversion_task(
        self, 
        task_data: ConversionTaskCreate, 
        user_id: str
    ) -> ConversionTaskInDB:
        """Create a new conversion task."""
        try:
            # Verify manuscript exists and belongs to user
            manuscript = await manuscript_service.get_manuscript_by_id(task_data.manuscript_id, user_id)
            if not manuscript:
                raise ValueError(f"Manuscript {task_data.manuscript_id} not found or access denied")
            
            # Check if manuscript is ready for conversion
            if manuscript.status != ManuscriptStatus.PENDING:
                raise ValueError(f"Manuscript must be in 'pending' status for conversion, current status: {manuscript.status}")
            
            # Check if conversion task already exists for this manuscript
            existing_task = await self._get_collection().find_one({
                "manuscript_id": task_data.manuscript_id,
                "status": {"$in": [ConversionStatus.PENDING, ConversionStatus.PROCESSING]}
            })
            
            if existing_task:
                raise ValueError(f"Conversion task already exists for manuscript {task_data.manuscript_id}")
            
            # Create conversion task
            task_in_db = ConversionTaskInDB(
                manuscript_id=task_data.manuscript_id,
                user_id=user_id,
                quality=task_data.quality,
                include_metadata=task_data.include_metadata,
                priority=task_data.priority,
                status=ConversionStatus.PENDING,
                created_at=datetime.utcnow()
            )
            
            # Insert into database
            result = await self._get_collection().insert_one(task_in_db.dict(by_alias=True))
            task_in_db.id = result.inserted_id
            
            logger.info(f"Created conversion task {task_in_db.id} for manuscript {task_data.manuscript_id}")
            return task_in_db
            
        except Exception as e:
            logger.error(f"Failed to create conversion task: {e}")
            raise

    async def get_conversion_task(self, task_id: str, user_id: Optional[str] = None) -> Optional[ConversionTaskInDB]:
        """Get a conversion task by ID."""
        try:
            query = {"_id": ObjectId(task_id)}
            if user_id:
                query["user_id"] = user_id
            
            task_data = await self._get_collection().find_one(query)
            if task_data:
                return ConversionTaskInDB.parse_obj(task_data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get conversion task {task_id}: {e}")
            return None

    async def update_conversion_task(
        self, 
        task_id: str, 
        update_data: ConversionTaskUpdate
    ) -> Optional[ConversionTaskInDB]:
        """Update a conversion task."""
        try:
            update_dict = update_data.dict(by_alias=True, exclude_unset=True)
            if not update_dict:
                return await self.get_conversion_task(task_id)
            
            result = await self._get_collection().find_one_and_update(
                {"_id": ObjectId(task_id)},
                {"$set": update_dict},
                return_document=True
            )
            
            if result:
                logger.info(f"Updated conversion task {task_id}")
                return ConversionTaskInDB.parse_obj(result)
            return None
            
        except Exception as e:
            logger.error(f"Failed to update conversion task {task_id}: {e}")
            return None

    async def get_user_conversion_tasks(
        self, 
        user_id: str, 
        page: int = 1, 
        size: int = 10,
        status: Optional[ConversionStatus] = None
    ) -> ConversionTaskListResponse:
        """Get conversion tasks for a specific user."""
        try:
            query = {"user_id": user_id}
            if status:
                query["status"] = status.value
            
            total_count = await self._get_collection().count_documents(query)
            
            cursor = self._get_collection().find(query).sort("created_at", -1).skip((page - 1) * size).limit(size)
            tasks_data = await cursor.to_list(length=size)
            
            tasks = [
                ConversionTaskResponse(
                    id=str(task["_id"]),
                    manuscript_id=task["manuscript_id"],
                    status=task["status"],
                    progress_percentage=task["progress_percentage"],
                    quality=task["quality"],
                    created_at=task["created_at"],
                    processing_started_at=task.get("processing_started_at"),
                    processing_completed_at=task.get("processing_completed_at"),
                    error_message=task.get("error_message"),
                    retry_count=task["retry_count"]
                )
                for task in tasks_data
            ]
            
            return ConversionTaskListResponse(
                tasks=tasks,
                total=total_count,
                page=page,
                size=size
            )
            
        except Exception as e:
            logger.error(f"Failed to get user conversion tasks: {e}")
            return ConversionTaskListResponse(tasks=[], total=0, page=page, size=size)

    async def get_next_pending_task(self) -> Optional[ConversionTaskInDB]:
        """Get the next pending conversion task with highest priority."""
        try:
            # Find and lock the next pending task
            current_time = datetime.utcnow()
            lock_expiry = current_time + timedelta(minutes=30)  # 30-minute lock
            
            result = await self._get_collection().find_one_and_update(
                {
                    "status": ConversionStatus.PENDING,
                    "$or": [
                        {"locked_by": None},
                        {"lock_expires_at": {"$lt": current_time}}  # Expired locks
                    ]
                },
                {
                    "$set": {
                        "locked_by": self.worker_id,
                        "locked_at": current_time,
                        "lock_expires_at": lock_expiry
                    }
                },
                sort=[("priority", -1), ("created_at", 1)],  # Highest priority first, then FIFO
                return_document=True
            )
            
            if result:
                logger.info(f"Locked conversion task {result['_id']} for processing")
                return ConversionTaskInDB.parse_obj(result)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get next pending task: {e}")
            return None

    async def process_conversion_task(self, task: ConversionTaskInDB) -> ConversionResult:
        """Process a conversion task with comprehensive error handling and logging."""
        task_id = str(task.id)
        
        # Create error context
        error_context = ErrorContext(
            operation="process_conversion_task",
            resource_id=task_id,
            user_id=task.user_id,
            additional_data={
                "manuscript_id": task.manuscript_id,
                "quality": task.quality.value,
                "priority": task.priority
            }
        )
        
        # Use logging context for structured logging
        with LoggingContext(
            operation="conversion_processing",
            user_id=task.user_id,
            conversion_id=task_id,
            manuscript_id=task.manuscript_id
        ) as log_ctx:
            
            start_time = datetime.utcnow()
            
            # Log conversion start
            conversion_logger.log_conversion_start(
                conversion_id=task_id,
                manuscript_id=task.manuscript_id,
                user_id=task.user_id,
                quality=task.quality.value,
                priority=task.priority
            )
            
            try:
                # Record status change for potential rollback
                rollback_manager.record_status_change(
                    resource_type="conversion_task",
                    resource_id=task_id,
                    old_status=ConversionStatus.PENDING.value,
                    new_status=ConversionStatus.PROCESSING.value,
                    rollback_function=self._rollback_task_status
                )
                
                # Update task status to processing
                await self.update_conversion_task(task_id, ConversionTaskUpdate(
                    status=ConversionStatus.PROCESSING,
                    processing_started_at=datetime.utcnow(),
                    progress_percentage=10
                ))
                
                conversion_logger.log_conversion_progress(
                    conversion_id=task_id,
                    manuscript_id=task.manuscript_id,
                    progress=10,
                    status="processing",
                    message="Task status updated to processing"
                )
                
                # Get manuscript details with error handling
                try:
                    manuscript = await manuscript_service.get_manuscript_by_id(task.manuscript_id, task.user_id)
                    if not manuscript:
                        raise BusinessLogicError(
                            message=f"Manuscript {task.manuscript_id} not found or access denied",
                            rule="manuscript_access_validation",
                            context=error_context
                        )
                except Exception as e:
                    raise DatabaseError(
                        message=f"Failed to retrieve manuscript {task.manuscript_id}",
                        collection="manuscripts",
                        operation="find_by_id",
                        context=error_context,
                        cause=e
                    )
                
                # Record manuscript status change for rollback
                rollback_manager.record_status_change(
                    resource_type="manuscript",
                    resource_id=task.manuscript_id,
                    old_status=manuscript.status.value,
                    new_status=ManuscriptStatus.PROCESSING.value,
                    rollback_function=self._rollback_manuscript_status
                )
                
                # Update progress
                await self.update_conversion_task(task_id, ConversionTaskUpdate(
                    progress_percentage=20
                ))
                
                conversion_logger.log_conversion_progress(
                    conversion_id=task_id,
                    manuscript_id=task.manuscript_id,
                    progress=20,
                    status="processing",
                    message="Manuscript retrieved and validated"
                )
                
                # Perform PDF to XML conversion with error handling
                try:
                    conversion_logger.log_conversion_progress(
                        conversion_id=task_id,
                        manuscript_id=task.manuscript_id,
                        progress=30,
                        status="processing",
                        message="Starting PDF to XML conversion"
                    )
                    
                    xml_s3_key, conversion_metadata = await docbook_conversion_service.convert_pdf_to_docbook(
                        pdf_s3_key=manuscript.pdf_s3_key,
                        output_filename=manuscript.file_name.replace('.pdf', '.xml'),
                        quality=task.quality.value,
                        include_metadata=task.include_metadata
                    )
                    
                except Exception as e:
                    raise ConversionError(
                        message=f"PDF to XML conversion failed",
                        conversion_id=task_id,
                        manuscript_id=task.manuscript_id,
                        context=error_context,
                        cause=e
                    )
                
                # Update progress
                await self.update_conversion_task(task_id, ConversionTaskUpdate(
                    progress_percentage=80
                ))
                
                conversion_logger.log_conversion_progress(
                    conversion_id=task_id,
                    manuscript_id=task.manuscript_id,
                    progress=80,
                    status="processing",
                    message="PDF conversion completed, updating manuscript"
                )
                
                # Update manuscript with XML key and status
                try:
                    await manuscript_service.update_manuscript(
                        task.manuscript_id, 
                        ManuscriptUpdate(
                            xml_s3_key=xml_s3_key,
                            status=ManuscriptStatus.COMPLETE,
                            processing_completed_at=datetime.utcnow()
                        )
                    )
                except Exception as e:
                    raise DatabaseError(
                        message=f"Failed to update manuscript {task.manuscript_id} with conversion results",
                        collection="manuscripts",
                        operation="update",
                        context=error_context,
                        cause=e
                    )
                
                # Complete the conversion task
                try:
                    await self.update_conversion_task(task_id, ConversionTaskUpdate(
                        status=ConversionStatus.COMPLETED,
                        progress_percentage=100,
                        xml_s3_key=xml_s3_key,
                        conversion_metadata=conversion_metadata,
                        processing_completed_at=datetime.utcnow()
                    ))
                except Exception as e:
                    raise DatabaseError(
                        message=f"Failed to update conversion task {task_id} completion status",
                        collection="conversion_tasks",
                        operation="update",
                        context=error_context,
                        cause=e
                    )
                
                # Calculate processing time
                end_time = datetime.utcnow()
                processing_time_seconds = (end_time - start_time).total_seconds()
                
                # Log performance metrics
                input_size_mb = conversion_metadata.get("pdf_info", {}).get("size_mb", 0)
                output_size_mb = conversion_metadata.get("conversion_stats", {}).get("output_size_mb", 0)
                
                performance_logger.log_conversion_performance(
                    conversion_id=task_id,
                    manuscript_id=task.manuscript_id,
                    duration_ms=processing_time_seconds * 1000,
                    input_size_mb=input_size_mb,
                    output_size_mb=output_size_mb,
                    status="success"
                )
                
                # Performance metrics recording removed
                
                # Log successful conversion
                conversion_logger.log_conversion_success(
                    conversion_id=task_id,
                    manuscript_id=task.manuscript_id,
                    xml_s3_key=xml_s3_key,
                    metadata=conversion_metadata
                )
                
                # Clear rollback stack on success
                rollback_manager.clear_rollback_stack()
                
                # Clear retry count on success
                retry_manager.clear_retry_count(task_id)
                
                # Create result
                result = ConversionResult(
                    task_id=task_id,
                    manuscript_id=task.manuscript_id,
                    status=ConversionStatus.COMPLETED,
                    xml_s3_key=xml_s3_key,
                    processing_time_seconds=processing_time_seconds,
                    input_file_size_mb=input_size_mb,
                    output_file_size_mb=output_size_mb,
                    quality=task.quality,
                    pages_processed=conversion_metadata.get("pdf_info", {}).get("pages", 0),
                    conversion_metadata=conversion_metadata
                )
                
                return result
                
            except Exception as e:
                # Handle error with comprehensive error handling
                app_error = error_handler.handle_error(e, error_context)
                
                # Calculate processing time for failed conversion
                end_time = datetime.utcnow()
                processing_time_seconds = (end_time - start_time).total_seconds()
                
                # Log conversion error
                conversion_logger.log_conversion_error(
                    conversion_id=task_id,
                    manuscript_id=task.manuscript_id,
                    error_code=app_error.error_code,
                    error_message=app_error.message,
                    retry_count=task.retry_count
                )
                
                # Performance metrics recording removed
                
                # Check if retry is possible
                should_retry = retry_manager.should_retry(app_error, task_id)
                
                if should_retry:
                    retry_count = retry_manager.record_retry(task_id)
                    
                    conversion_logger.log_conversion_retry(
                        conversion_id=task_id,
                        manuscript_id=task.manuscript_id,
                        retry_count=retry_count,
                        max_retries=retry_manager.max_retries,
                        reason=app_error.message
                    )
                    
                    # Update task for retry
                    await self.update_conversion_task(task_id, ConversionTaskUpdate(
                        status=ConversionStatus.PENDING,
                        error_message=None,
                        retry_count=retry_count,
                        processing_started_at=None,
                        processing_completed_at=None,
                        locked_by=None,
                        locked_at=None,
                        lock_expires_at=None
                    ))
                    
                    # Rollback status changes
                    await rollback_manager.rollback_on_error(app_error)
                    
                else:
                    # Update task with permanent failure
                    await self.update_conversion_task(task_id, ConversionTaskUpdate(
                        status=ConversionStatus.FAILED,
                        error_message=app_error.message,
                        processing_completed_at=datetime.utcnow(),
                        retry_count=task.retry_count + 1
                    ))
                    
                    # Update manuscript status to failed
                    try:
                        await manuscript_service.update_manuscript(
                            task.manuscript_id, 
                            ManuscriptUpdate(
                                status=ManuscriptStatus.FAILED,
                                error_message=app_error.message,
                                processing_completed_at=datetime.utcnow()
                            )
                        )
                    except Exception as update_error:
                        logger.error(f"Failed to update manuscript status to failed: {update_error}")
                
                # Create error result
                result = ConversionResult(
                    task_id=task_id,
                    manuscript_id=task.manuscript_id,
                    status=ConversionStatus.FAILED if not should_retry else ConversionStatus.PENDING,
                    error_message=app_error.message,
                    processing_time_seconds=processing_time_seconds,
                    input_file_size_mb=0,
                    quality=task.quality,
                    pages_processed=0
                )
                
                return result
    
    async def _rollback_task_status(self, task_id: str, old_status: str) -> None:
        """Rollback task status."""
        try:
            await self.update_conversion_task(task_id, ConversionTaskUpdate(
                status=ConversionStatus(old_status)
            ))
        except Exception as e:
            logger.error(f"Failed to rollback task status for {task_id}: {e}")
    
    async def _rollback_manuscript_status(self, manuscript_id: str, old_status: str) -> None:
        """Rollback manuscript status."""
        try:
            await manuscript_service.update_manuscript(
                manuscript_id, 
                ManuscriptUpdate(status=ManuscriptStatus(old_status))
            )
        except Exception as e:
            logger.error(f"Failed to rollback manuscript status for {manuscript_id}: {e}")

    async def retry_conversion_task(self, task_id: str, user_id: str) -> bool:
        """Retry a failed conversion task."""
        try:
            task = await self.get_conversion_task(task_id, user_id)
            if not task:
                return False
            
            if task.status != ConversionStatus.FAILED:
                raise ValueError("Only failed tasks can be retried")
            
            if task.retry_count >= task.max_retries:
                raise ValueError("Maximum retry attempts exceeded")
            
            # Reset task for retry
            await self.update_conversion_task(task_id, ConversionTaskUpdate(
                status=ConversionStatus.PENDING,
                progress_percentage=0,
                error_message=None,
                processing_started_at=None,
                processing_completed_at=None,
                locked_by=None,
                locked_at=None,
                lock_expires_at=None
            ))
            
            logger.info(f"Conversion task {task_id} queued for retry")
            return True
            
        except Exception as e:
            logger.error(f"Failed to retry conversion task {task_id}: {e}")
            return False

    async def cancel_conversion_task(self, task_id: str, user_id: str) -> bool:
        """Cancel a conversion task."""
        try:
            task = await self.get_conversion_task(task_id, user_id)
            if not task:
                return False
            
            if task.status in [ConversionStatus.COMPLETED, ConversionStatus.CANCELLED]:
                return False  # Already completed or cancelled
            
            await self.update_conversion_task(task_id, ConversionTaskUpdate(
                status=ConversionStatus.CANCELLED,
                processing_completed_at=datetime.utcnow()
            ))
            
            logger.info(f"Conversion task {task_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel conversion task {task_id}: {e}")
            return False

    async def get_conversion_statistics(self, user_id: Optional[str] = None) -> ConversionStatistics:
        """Get conversion statistics."""
        try:
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            # Aggregate statistics
            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_processing_time": {
                        "$avg": {
                            "$subtract": ["$processing_completed_at", "$processing_started_at"]
                        }
                    }
                }}
            ]
            
            status_results = await self._get_collection().aggregate(pipeline).to_list(length=None)
            
            # Initialize statistics
            stats = ConversionStatistics(
                total_conversions=0,
                status_counts={},
                pending=0,
                processing=0,
                completed=0,
                failed=0,
                cancelled=0,
                quality_distribution={}
            )
            
            # Process results
            for result in status_results:
                status = result["_id"]
                count = result["count"]
                stats.status_counts[status] = count
                stats.total_conversions += count
                
                if status == ConversionStatus.PENDING:
                    stats.pending = count
                elif status == ConversionStatus.PROCESSING:
                    stats.processing = count
                elif status == ConversionStatus.COMPLETED:
                    stats.completed = count
                elif status == ConversionStatus.FAILED:
                    stats.failed = count
                elif status == ConversionStatus.CANCELLED:
                    stats.cancelled = count
            
            # Calculate success rate
            if stats.total_conversions > 0:
                stats.success_rate_percentage = (stats.completed / stats.total_conversions) * 100
            
            # Get quality distribution
            quality_pipeline = [
                {"$match": query},
                {"$group": {"_id": "$quality", "count": {"$sum": 1}}}
            ]
            
            quality_results = await self._get_collection().aggregate(quality_pipeline).to_list(length=None)
            for result in quality_results:
                stats.quality_distribution[result["_id"]] = result["count"]
            
            # Get recent activity
            now = datetime.utcnow()
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)
            
            stats.conversions_last_24h = await self._get_collection().count_documents({
                **query,
                "created_at": {"$gte": last_24h}
            })
            
            stats.conversions_last_7d = await self._get_collection().count_documents({
                **query,
                "created_at": {"$gte": last_7d}
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get conversion statistics: {e}")
            return ConversionStatistics(
                total_conversions=0,
                status_counts={},
                pending=0,
                processing=0,
                completed=0,
                failed=0,
                cancelled=0
            )

    async def cleanup_expired_locks(self) -> int:
        """Clean up expired task locks."""
        try:
            current_time = datetime.utcnow()
            
            result = await self._get_collection().update_many(
                {
                    "status": ConversionStatus.PROCESSING,
                    "lock_expires_at": {"$lt": current_time}
                },
                {
                    "$set": {
                        "status": ConversionStatus.PENDING,
                        "locked_by": None,
                        "locked_at": None,
                        "lock_expires_at": None
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Cleaned up {result.modified_count} expired task locks")
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired locks: {e}")
            return 0

# Global service instance
conversion_service = ConversionService()
