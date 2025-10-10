"""
Extended user management service.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user_management import (
    ExtendedUserInDB, ExtendedUserResponse, UserProfileUpdate,
    PasswordChangeRequest, PasswordResetRequest, AdminUserUpdate,
    UserListFilter, UserStatistics, UserRole, ActivityType
)
from app.core.database import get_database
from app.core.collections import Collections
from app.core.security import get_password_hash, verify_password
from app.services.user_service import user_service
from app.services.activity_service import activity_service
import logging

logger = logging.getLogger(__name__)


class UserManagementService:
    """Extended service for user management operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase = None):
        self.db = db
    
    def _get_collection(self):
        """Get the users collection."""
        if self.db is None:
            self.db = get_database()
        return self.db[Collections.USERS]
    
    async def update_user_profile(
        self,
        user_id: str,
        profile_data: UserProfileUpdate,
        request=None
    ) -> Optional[ExtendedUserResponse]:
        """
        Update user profile information.
        
        Args:
            user_id: User ID
            profile_data: Profile update data
            request: FastAPI request object for activity logging
            
        Returns:
            ExtendedUserResponse: Updated user information
        """
        try:
            collection = self._get_collection()
            object_id = ObjectId(user_id)
            
            update_dict = {}
            changes = []
            
            # Build update dictionary
            if profile_data.email is not None:
                # Check if new email is already taken
                existing_user = await collection.find_one(
                    {"email": profile_data.email, "_id": {"$ne": object_id}}
                )
                if existing_user:
                    raise ValueError("Email already taken by another user")
                update_dict["email"] = profile_data.email
                changes.append("email")
            
            if profile_data.first_name is not None:
                update_dict["first_name"] = profile_data.first_name.strip()
                changes.append("first_name")
            
            if profile_data.last_name is not None:
                update_dict["last_name"] = profile_data.last_name.strip()
                changes.append("last_name")
            
            if update_dict:
                update_dict["updated_at"] = datetime.utcnow()
                
                # Update user in database
                result = await collection.update_one(
                    {"_id": object_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count > 0:
                    # Log activity
                    await activity_service.log_activity(
                        user_id=user_id,
                        activity_type=ActivityType.PROFILE_UPDATE,
                        description=f"Profile updated: {', '.join(changes)}",
                        request=request,
                        metadata={"updated_fields": changes}
                    )
                    
                    # Return updated user
                    updated_user = await self.get_user_by_id(user_id)
                    logger.info(f"Profile updated for user {user_id}: {changes}")
                    return updated_user
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating user profile {user_id}: {e}")
            raise
    
    async def change_password(
        self,
        user_id: str,
        password_data: PasswordChangeRequest,
        request=None
    ) -> bool:
        """
        Change user password.
        
        Args:
            user_id: User ID
            password_data: Password change data
            request: FastAPI request object for activity logging
            
        Returns:
            bool: True if password changed successfully
        """
        try:
            collection = self._get_collection()
            object_id = ObjectId(user_id)
            
            # Get current user
            user_doc = await collection.find_one({"_id": object_id})
            if not user_doc:
                raise ValueError("User not found")
            
            # Verify current password
            if not verify_password(password_data.current_password, user_doc["password_hash"]):
                raise ValueError("Current password is incorrect")
            
            # Update password
            new_password_hash = get_password_hash(password_data.new_password)
            result = await collection.update_one(
                {"_id": object_id},
                {"$set": {
                    "password_hash": new_password_hash,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            if result.modified_count > 0:
                # Log activity
                await activity_service.log_activity(
                    user_id=user_id,
                    activity_type=ActivityType.PASSWORD_CHANGE,
                    description="Password changed successfully",
                    request=request
                )
                
                logger.info(f"Password changed for user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error changing password for user {user_id}: {e}")
            raise
    
    async def request_password_reset(
        self,
        email: str,
        request=None
    ) -> Optional[str]:
        """
        Request password reset token.
        
        Args:
            email: User email
            request: FastAPI request object for activity logging
            
        Returns:
            str: Reset token (in production, send via email)
        """
        try:
            collection = self._get_collection()
            
            # Find user by email
            user_doc = await collection.find_one({"email": email})
            if not user_doc:
                # Don't reveal if email exists or not
                logger.warning(f"Password reset requested for non-existent email: {email}")
                return None
            
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            reset_expires = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
            
            # Update user with reset token
            result = await collection.update_one(
                {"_id": user_doc["_id"]},
                {"$set": {
                    "reset_token": reset_token,
                    "reset_token_expires": reset_expires,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            if result.modified_count > 0:
                # Log activity
                await activity_service.log_activity(
                    user_id=str(user_doc["_id"]),
                    activity_type=ActivityType.PASSWORD_RESET,
                    description="Password reset requested",
                    request=request
                )
                
                logger.info(f"Password reset token generated for user {email}")
                return reset_token
            
            return None
            
        except Exception as e:
            logger.error(f"Error requesting password reset for {email}: {e}")
            return None
    
    async def reset_password(
        self,
        token: str,
        new_password: str,
        request=None
    ) -> bool:
        """
        Reset password using token.
        
        Args:
            token: Reset token
            new_password: New password
            request: FastAPI request object for activity logging
            
        Returns:
            bool: True if password reset successfully
        """
        try:
            collection = self._get_collection()
            
            # Find user by reset token
            user_doc = await collection.find_one({
                "reset_token": token,
                "reset_token_expires": {"$gt": datetime.utcnow()}
            })
            
            if not user_doc:
                logger.warning(f"Invalid or expired reset token: {token}")
                return False
            
            # Update password and clear reset token
            new_password_hash = get_password_hash(new_password)
            result = await collection.update_one(
                {"_id": user_doc["_id"]},
                {"$set": {
                    "password_hash": new_password_hash,
                    "updated_at": datetime.utcnow()
                }, "$unset": {
                    "reset_token": "",
                    "reset_token_expires": ""
                }}
            )
            
            if result.modified_count > 0:
                # Log activity
                await activity_service.log_activity(
                    user_id=str(user_doc["_id"]),
                    activity_type=ActivityType.PASSWORD_RESET,
                    description="Password reset completed",
                    request=request
                )
                
                logger.info(f"Password reset completed for user {user_doc['email']}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return False
    
    async def get_user_by_id(self, user_id: str) -> Optional[ExtendedUserResponse]:
        """Get extended user information by ID."""
        try:
            collection = self._get_collection()
            object_id = ObjectId(user_id)
            user_doc = await collection.find_one({"_id": object_id})
            
            if user_doc:
                return self._doc_to_response(user_doc)
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    async def list_users(
        self,
        filters: UserListFilter,
        skip: int = 0,
        limit: int = 50
    ) -> List[ExtendedUserResponse]:
        """
        List users with filtering.
        
        Args:
            filters: User list filters
            skip: Number of users to skip
            limit: Maximum number of users to return
            
        Returns:
            List[ExtendedUserResponse]: List of users
        """
        try:
            collection = self._get_collection()
            
            # Build query
            query = {}
            
            if filters.role is not None:
                query["role"] = filters.role
            
            if filters.is_active is not None:
                query["is_active"] = filters.is_active
            
            if filters.is_verified is not None:
                query["is_verified"] = filters.is_verified
            
            if filters.search:
                # Search in email, first_name, last_name
                search_regex = {"$regex": filters.search, "$options": "i"}
                query["$or"] = [
                    {"email": search_regex},
                    {"first_name": search_regex},
                    {"last_name": search_regex}
                ]
            
            if filters.created_after:
                query.setdefault("created_at", {})["$gte"] = filters.created_after
            
            if filters.created_before:
                query.setdefault("created_at", {})["$lte"] = filters.created_before
            
            # Get users
            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            users = await cursor.to_list(length=limit)
            
            return [self._doc_to_response(user) for user in users]
            
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []
    
    async def update_user_admin(
        self,
        user_id: str,
        admin_data: AdminUserUpdate,
        admin_user_id: str,
        request=None
    ) -> Optional[ExtendedUserResponse]:
        """
        Admin update user information.
        
        Args:
            user_id: User ID to update
            admin_data: Admin update data
            admin_user_id: ID of admin performing the update
            request: FastAPI request object for activity logging
            
        Returns:
            ExtendedUserResponse: Updated user information
        """
        try:
            collection = self._get_collection()
            object_id = ObjectId(user_id)
            
            update_dict = {}
            changes = []
            
            # Build update dictionary
            if admin_data.email is not None:
                # Check if new email is already taken
                existing_user = await collection.find_one(
                    {"email": admin_data.email, "_id": {"$ne": object_id}}
                )
                if existing_user:
                    raise ValueError("Email already taken by another user")
                update_dict["email"] = admin_data.email
                changes.append("email")
            
            if admin_data.first_name is not None:
                update_dict["first_name"] = admin_data.first_name.strip()
                changes.append("first_name")
            
            if admin_data.last_name is not None:
                update_dict["last_name"] = admin_data.last_name.strip()
                changes.append("last_name")
            
            if admin_data.is_active is not None:
                update_dict["is_active"] = admin_data.is_active
                changes.append("is_active")
            
            if admin_data.is_verified is not None:
                update_dict["is_verified"] = admin_data.is_verified
                changes.append("is_verified")
            
            if admin_data.role is not None:
                update_dict["role"] = admin_data.role
                changes.append("role")
            
            if update_dict:
                update_dict["updated_at"] = datetime.utcnow()
                
                # Update user in database
                result = await collection.update_one(
                    {"_id": object_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count > 0:
                    # Log activity for both users
                    await activity_service.log_activity(
                        user_id=user_id,
                        activity_type=ActivityType.PROFILE_UPDATE,
                        description=f"Profile updated by admin: {', '.join(changes)}",
                        request=request,
                        metadata={"updated_by": admin_user_id, "updated_fields": changes}
                    )
                    
                    # Return updated user
                    updated_user = await self.get_user_by_id(user_id)
                    logger.info(f"User {user_id} updated by admin {admin_user_id}: {changes}")
                    return updated_user
            
            return None
            
        except Exception as e:
            logger.error(f"Error admin updating user {user_id}: {e}")
            raise
    
    async def get_user_statistics(self) -> UserStatistics:
        """Get user statistics."""
        try:
            collection = self._get_collection()
            
            # Get current date boundaries
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            month_start = today_start - timedelta(days=30)
            
            # Aggregate statistics
            pipeline = [
                {
                    "$facet": {
                        "total_users": [{"$count": "count"}],
                        "active_users": [
                            {"$match": {"is_active": True}},
                            {"$count": "count"}
                        ],
                        "verified_users": [
                            {"$match": {"is_verified": True}},
                            {"$count": "count"}
                        ],
                        "admin_users": [
                            {"$match": {"role": {"$in": ["admin", "super_admin"]}}},
                            {"$count": "count"}
                        ],
                        "users_today": [
                            {"$match": {"created_at": {"$gte": today_start}}},
                            {"$count": "count"}
                        ],
                        "users_this_week": [
                            {"$match": {"created_at": {"$gte": week_start}}},
                            {"$count": "count"}
                        ],
                        "users_this_month": [
                            {"$match": {"created_at": {"$gte": month_start}}},
                            {"$count": "count"}
                        ],
                        "total_logins": [
                            {"$group": {"_id": None, "total": {"$sum": "$login_count"}}}
                        ],
                        "total_manuscripts": [
                            {"$group": {"_id": None, "total": {"$sum": "$manuscript_count"}}}
                        ]
                    }
                }
            ]
            
            cursor = collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if result:
                stats = result[0]
                return UserStatistics(
                    total_users=stats["total_users"][0]["count"] if stats["total_users"] else 0,
                    active_users=stats["active_users"][0]["count"] if stats["active_users"] else 0,
                    verified_users=stats["verified_users"][0]["count"] if stats["verified_users"] else 0,
                    admin_users=stats["admin_users"][0]["count"] if stats["admin_users"] else 0,
                    users_today=stats["users_today"][0]["count"] if stats["users_today"] else 0,
                    users_this_week=stats["users_this_week"][0]["count"] if stats["users_this_week"] else 0,
                    users_this_month=stats["users_this_month"][0]["count"] if stats["users_this_month"] else 0,
                    total_logins=stats["total_logins"][0]["total"] if stats["total_logins"] else 0,
                    total_manuscripts=stats["total_manuscripts"][0]["total"] if stats["total_manuscripts"] else 0
                )
            
            return UserStatistics(
                total_users=0, active_users=0, verified_users=0, admin_users=0,
                users_today=0, users_this_week=0, users_this_month=0,
                total_logins=0, total_manuscripts=0
            )
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return UserStatistics(
                total_users=0, active_users=0, verified_users=0, admin_users=0,
                users_today=0, users_this_week=0, users_this_month=0,
                total_logins=0, total_manuscripts=0
            )
    
    def _doc_to_response(self, user_doc: dict) -> ExtendedUserResponse:
        """Convert user document to response model."""
        return ExtendedUserResponse(
            id=str(user_doc["_id"]),
            email=user_doc["email"],
            first_name=user_doc.get("first_name"),
            last_name=user_doc.get("last_name"),
            is_active=user_doc.get("is_active", True),
            is_verified=user_doc.get("is_verified", False),
            role=user_doc.get("role", UserRole.USER),
            created_at=user_doc["created_at"],
            updated_at=user_doc.get("updated_at"),
            last_login=user_doc.get("last_login"),
            login_count=user_doc.get("login_count", 0),
            manuscript_count=user_doc.get("manuscript_count", 0)
        )


# Global user management service instance
user_management_service = UserManagementService()
