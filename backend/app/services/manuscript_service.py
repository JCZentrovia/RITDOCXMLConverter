"""
Manuscript service for database operations.
"""
import logging
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.core.collections import Collections
from app.models.manuscript import (
    ManuscriptCreate, 
    ManuscriptUpdate, 
    ManuscriptInDB, 
    Manuscript,
    ManuscriptStatus
)

logger = logging.getLogger(__name__)


class ManuscriptService:
    """Service for manuscript database operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase = None):
        self.db = db
    
    def _get_collection(self):
        """Get the manuscripts collection."""
        if self.db is None:
            self.db = get_database()
        return self.db[Collections.MANUSCRIPTS]
    
    async def create_manuscript(self, manuscript_data: ManuscriptCreate) -> ManuscriptInDB:
        """
        Create a new manuscript record in the database.
        
        Args:
            manuscript_data: Manuscript creation data
            
        Returns:
            Created manuscript document
            
        Raises:
            Exception: If creation fails
        """
        try:
            collection = self._get_collection()
            
            # Convert user_id string to ObjectId
            user_object_id = ObjectId(manuscript_data.user_id)
            
            # Create manuscript document
            manuscript_doc = {
                "user_id": user_object_id,
                "file_name": manuscript_data.file_name,
                "pdf_s3_key": manuscript_data.pdf_s3_key,
                "epub_s3_key": manuscript_data.epub_s3_key,
                "status": ManuscriptStatus.PENDING,
                "upload_date": datetime.utcnow(),
                "content_type": "application/pdf",
                "retry_count": 0
            }
            
            # Insert document
            result = await collection.insert_one(manuscript_doc)
            
            # Retrieve and return the created document
            created_doc = await collection.find_one({"_id": result.inserted_id})
            
            logger.info(f"Created manuscript: {result.inserted_id}")
            return ManuscriptInDB(**created_doc)
            
        except Exception as e:
            logger.error(f"Failed to create manuscript: {e}")
            raise
    
    async def get_manuscript_by_id(self, manuscript_id: str, user_id: str = None) -> Optional[ManuscriptInDB]:
        """
        Get a manuscript by ID.
        
        Args:
            manuscript_id: Manuscript ID
            user_id: Optional user ID for ownership check
            
        Returns:
            Manuscript document or None if not found
        """
        try:
            collection = self._get_collection()
            
            # Build query
            query = {"_id": ObjectId(manuscript_id)}
            if user_id:
                query["user_id"] = ObjectId(user_id)
            
            # Find manuscript
            manuscript_doc = await collection.find_one(query)
            
            if manuscript_doc:
                return ManuscriptInDB(**manuscript_doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get manuscript {manuscript_id}: {e}")
            return None
    
    async def get_manuscripts_by_user(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 50,
        status: Optional[ManuscriptStatus] = None
    ) -> List[ManuscriptInDB]:
        """
        Get manuscripts for a specific user.
        
        Args:
            user_id: User ID
            skip: Number of documents to skip (pagination)
            limit: Maximum number of documents to return
            status: Optional status filter
            
        Returns:
            List of manuscript documents
        """
        try:
            collection = self._get_collection()
            
            # Build query
            query = {"user_id": ObjectId(user_id)}
            if status:
                query["status"] = status
            
            # Execute query with pagination
            cursor = collection.find(query).skip(skip).limit(limit).sort("upload_date", -1)
            manuscripts = []
            
            async for doc in cursor:
                manuscripts.append(ManuscriptInDB(**doc))
            
            logger.info(f"Retrieved {len(manuscripts)} manuscripts for user {user_id}")
            return manuscripts
            
        except Exception as e:
            logger.error(f"Failed to get manuscripts for user {user_id}: {e}")
            return []
    
    async def count_manuscripts_by_user(
        self, 
        user_id: str, 
        status: Optional[ManuscriptStatus] = None
    ) -> int:
        """
        Count manuscripts for a specific user.
        
        Args:
            user_id: User ID
            status: Optional status filter
            
        Returns:
            Count of manuscripts
        """
        try:
            collection = self._get_collection()
            
            # Build query
            query = {"user_id": ObjectId(user_id)}
            if status:
                query["status"] = status
            
            count = await collection.count_documents(query)
            return count
            
        except Exception as e:
            logger.error(f"Failed to count manuscripts for user {user_id}: {e}")
            return 0
    
    async def update_manuscript(
        self, 
        manuscript_id: str, 
        update_data: ManuscriptUpdate,
        user_id: str = None
    ) -> Optional[ManuscriptInDB]:
        """
        Update a manuscript.
        
        Args:
            manuscript_id: Manuscript ID
            update_data: Update data
            user_id: Optional user ID for ownership check
            
        Returns:
            Updated manuscript document or None if not found
        """
        try:
            collection = self._get_collection()
            
            # Build query
            query = {"_id": ObjectId(manuscript_id)}
            if user_id:
                query["user_id"] = ObjectId(user_id)
            
            # Build update document
            update_doc = {}
            if update_data.status is not None:
                update_doc["status"] = update_data.status
            if update_data.docx_s3_key is not None:
                update_doc["docx_s3_key"] = update_data.docx_s3_key
            if getattr(update_data, "xml_s3_key", None) is not None:
               update_doc["xml_s3_key"] = update_data.xml_s3_key
            if update_data.processing_started_at is not None:
                update_doc["processing_started_at"] = update_data.processing_started_at
            if update_data.processing_completed_at is not None:
                update_doc["processing_completed_at"] = update_data.processing_completed_at
            if update_data.error_message is not None:
                update_doc["error_message"] = update_data.error_message
            
            if not update_doc:
                # No updates to apply
                return await self.get_manuscript_by_id(manuscript_id, user_id)
            
            # Update document
            result = await collection.update_one(
                query,
                {"$set": update_doc}
            )
            
            if result.matched_count == 0:
                return None
            
            # Return updated document
            updated_doc = await collection.find_one(query)
            logger.info(f"Updated manuscript: {manuscript_id}")
            return ManuscriptInDB(**updated_doc)
            
        except Exception as e:
            logger.error(f"Failed to update manuscript {manuscript_id}: {e}")
            return None
    
    async def delete_manuscript(self, manuscript_id: str, user_id: str = None) -> bool:
        """
        Delete a manuscript.
        
        Args:
            manuscript_id: Manuscript ID
            user_id: Optional user ID for ownership check
            
        Returns:
            True if deleted, False if not found
        """
        try:
            collection = self._get_collection()
            
            # Build query
            query = {"_id": ObjectId(manuscript_id)}
            if user_id:
                query["user_id"] = ObjectId(user_id)
            
            # Delete document
            result = await collection.delete_one(query)
            
            if result.deleted_count > 0:
                logger.info(f"Deleted manuscript: {manuscript_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete manuscript {manuscript_id}: {e}")
            return False
    
    async def get_pending_manuscripts(self, limit: int = 10) -> List[ManuscriptInDB]:
        """
        Get pending manuscripts for processing.
        
        Args:
            limit: Maximum number of manuscripts to return
            
        Returns:
            List of pending manuscript documents
        """
        try:
            collection = self._get_collection()
            
            # Find pending manuscripts, oldest first
            cursor = collection.find(
                {"status": ManuscriptStatus.PENDING}
            ).sort("upload_date", 1).limit(limit)
            
            manuscripts = []
            async for doc in cursor:
                manuscripts.append(ManuscriptInDB(**doc))
            
            logger.info(f"Retrieved {len(manuscripts)} pending manuscripts")
            return manuscripts
            
        except Exception as e:
            logger.error(f"Failed to get pending manuscripts: {e}")
            return []
    
    async def increment_retry_count(self, manuscript_id: str) -> bool:
        """
        Increment the retry count for a manuscript.
        
        Args:
            manuscript_id: Manuscript ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            collection = self._get_collection()
            
            result = await collection.update_one(
                {"_id": ObjectId(manuscript_id)},
                {"$inc": {"retry_count": 1}}
            )
            
            return result.matched_count > 0
            
        except Exception as e:
            logger.error(f"Failed to increment retry count for manuscript {manuscript_id}: {e}")
            return False
    
    async def get_manuscript_statistics(self) -> dict:
        """
        Get manuscript processing statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            collection = self._get_collection()
            
            # Aggregate statistics
            pipeline = [
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            cursor = collection.aggregate(pipeline)
            stats = {"total": 0}
            
            async for doc in cursor:
                status = doc["_id"]
                count = doc["count"]
                stats[status] = count
                stats["total"] += count
            
            # Ensure all statuses are represented
            for status in ManuscriptStatus:
                if status.value not in stats:
                    stats[status.value] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get manuscript statistics: {e}")
            return {"total": 0, "pending": 0, "processing": 0, "complete": 0, "failed": 0}


# Global manuscript service instance
manuscript_service = ManuscriptService()
