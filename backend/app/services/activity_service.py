"""
User activity logging service.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Request

from app.models.user_management import UserActivityLog, ActivityType, UserActivityResponse
from app.core.database import get_database
from app.core.collections import Collections
import logging

logger = logging.getLogger(__name__)


class ActivityService:
    """Service for user activity logging and retrieval."""
    
    def __init__(self, db: AsyncIOMotorDatabase = None):
        self.db = db
    
    def _get_collection(self):
        """Get the activity logs collection."""
        if self.db is None:
            self.db = get_database()
        return self.db["user_activities"]  # New collection for activity logs
    
    async def log_activity(
        self,
        user_id: str,
        activity_type: ActivityType,
        description: str,
        request: Optional[Request] = None,
        metadata: Optional[dict] = None
    ) -> UserActivityLog:
        """
        Log user activity.
        
        Args:
            user_id: User ID
            activity_type: Type of activity
            description: Activity description
            request: FastAPI request object (for IP and user agent)
            metadata: Additional metadata
            
        Returns:
            UserActivityLog: Created activity log
        """
        try:
            # Extract request information
            ip_address = None
            user_agent = None
            
            if request:
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")
            
            # Create activity log
            activity_data = {
                "user_id": ObjectId(user_id),
                "activity_type": activity_type,
                "description": description,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow()
            }
            
            collection = self._get_collection()
            result = await collection.insert_one(activity_data)
            activity_data["_id"] = result.inserted_id
            
            logger.info(f"Activity logged: {activity_type} for user {user_id}")
            return UserActivityLog(**activity_data)
            
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
            # Don't raise exception to avoid breaking main functionality
            return None
    
    async def get_user_activities(
        self,
        user_id: str,
        activity_type: Optional[ActivityType] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[UserActivityResponse]:
        """
        Get user activities.
        
        Args:
            user_id: User ID
            activity_type: Filter by activity type
            limit: Maximum number of activities to return
            skip: Number of activities to skip
            
        Returns:
            List[UserActivityResponse]: List of user activities
        """
        try:
            collection = self._get_collection()
            
            # Build query
            query = {"user_id": ObjectId(user_id)}
            if activity_type:
                query["activity_type"] = activity_type
            
            # Get activities
            cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
            activities = await cursor.to_list(length=limit)
            
            # Convert to response models
            return [
                UserActivityResponse(
                    id=str(activity["_id"]),
                    activity_type=activity["activity_type"],
                    description=activity["description"],
                    ip_address=activity.get("ip_address"),
                    timestamp=activity["timestamp"]
                )
                for activity in activities
            ]
            
        except Exception as e:
            logger.error(f"Failed to get user activities: {e}")
            return []
    
    async def get_recent_activities(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[UserActivityResponse]:
        """
        Get recent activities across all users.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of activities to return
            
        Returns:
            List[UserActivityResponse]: List of recent activities
        """
        try:
            collection = self._get_collection()
            
            # Calculate time threshold
            time_threshold = datetime.utcnow() - timedelta(hours=hours)
            
            # Get recent activities
            cursor = collection.find(
                {"timestamp": {"$gte": time_threshold}}
            ).sort("timestamp", -1).limit(limit)
            
            activities = await cursor.to_list(length=limit)
            
            # Convert to response models
            return [
                UserActivityResponse(
                    id=str(activity["_id"]),
                    activity_type=activity["activity_type"],
                    description=activity["description"],
                    ip_address=activity.get("ip_address"),
                    timestamp=activity["timestamp"]
                )
                for activity in activities
            ]
            
        except Exception as e:
            logger.error(f"Failed to get recent activities: {e}")
            return []
    
    async def get_activity_stats(
        self,
        user_id: Optional[str] = None,
        days: int = 30
    ) -> dict:
        """
        Get activity statistics.
        
        Args:
            user_id: User ID (if None, get stats for all users)
            days: Number of days to analyze
            
        Returns:
            dict: Activity statistics
        """
        try:
            collection = self._get_collection()
            
            # Calculate time threshold
            time_threshold = datetime.utcnow() - timedelta(days=days)
            
            # Build base query
            base_query = {"timestamp": {"$gte": time_threshold}}
            if user_id:
                base_query["user_id"] = ObjectId(user_id)
            
            # Aggregate activity counts by type
            pipeline = [
                {"$match": base_query},
                {"$group": {
                    "_id": "$activity_type",
                    "count": {"$sum": 1}
                }}
            ]
            
            cursor = collection.aggregate(pipeline)
            activity_counts = {doc["_id"]: doc["count"] async for doc in cursor}
            
            # Get total activity count
            total_activities = await collection.count_documents(base_query)
            
            return {
                "total_activities": total_activities,
                "activity_counts": activity_counts,
                "period_days": days,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"Failed to get activity stats: {e}")
            return {}
    
    async def cleanup_old_activities(self, days_to_keep: int = 90) -> int:
        """
        Clean up old activity logs.
        
        Args:
            days_to_keep: Number of days of activities to keep
            
        Returns:
            int: Number of activities deleted
        """
        try:
            collection = self._get_collection()
            
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Delete old activities
            result = await collection.delete_many(
                {"timestamp": {"$lt": cutoff_date}}
            )
            
            deleted_count = result.deleted_count
            logger.info(f"Cleaned up {deleted_count} old activity logs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old activities: {e}")
            return 0


# Global activity service instance
activity_service = ActivityService()
