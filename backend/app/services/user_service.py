"""
User service for database operations.
"""
from typing import Optional
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import UserCreate, UserUpdate, UserInDB, User, PyObjectId
from app.core.database import get_database
from app.core.collections import Collections
from app.core.security import get_password_hash, verify_password
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Service for user database operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase = None):
        self.db = db
    
    def _get_collection(self):
        """Get the users collection."""
        if self.db is None:
            self.db = get_database()
        return self.db[Collections.USERS]
    
    async def create_user(self, user_data: UserCreate) -> UserInDB:
        """Create a new user."""
        # Check if user already exists
        existing_user = await self.get_user_by_email(user_data.email)
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Hash password and create user document
        user_dict = {
            "email": user_data.email,
            "password_hash": get_password_hash(user_data.password),
            "created_at": datetime.utcnow(),
            "is_active": False  # Users start inactive and must be manually approved
        }
        
        # Insert user into database
        collection = self._get_collection()
        result = await collection.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id
        
        logger.info(f"Created user: {user_data.email}")
        return UserInDB(**user_dict)
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Get user by ID."""
        try:
            object_id = ObjectId(user_id)
            collection = self._get_collection()
            user_doc = await collection.find_one({"_id": object_id})
            
            if user_doc:
                return UserInDB(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get user by email."""
        try:
            collection = self._get_collection()
            user_doc = await collection.find_one({"email": email})
            
            if user_doc:
                return UserInDB(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        """Authenticate user with email and password."""
        user = await self.get_user_by_email(email)
        
        if not user:
            logger.warning(f"Authentication failed: User not found for email {email}")
            return None
        
        if not user.is_active:
            logger.warning(f"Authentication failed: User {email} is not active")
            return None
        
        if not verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: Invalid password for email {email}")
            return None
        
        logger.info(f"User authenticated successfully: {email}")
        return user
    
    async def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[UserInDB]:
        """Update user information."""
        try:
            object_id = ObjectId(user_id)
            update_dict = {}
            
            # Build update dictionary
            if user_data.email is not None:
                # Check if new email is already taken
                existing_user = await self.get_user_by_email(user_data.email)
                if existing_user and str(existing_user.id) != user_id:
                    raise ValueError("Email already taken by another user")
                update_dict["email"] = user_data.email
            
            if user_data.password is not None:
                update_dict["password_hash"] = get_password_hash(user_data.password)
            
            if update_dict:
                update_dict["updated_at"] = datetime.utcnow()
                
                # Update user in database
                collection = self._get_collection()
                result = await collection.update_one(
                    {"_id": object_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count > 0:
                    # Return updated user
                    return await self.get_user_by_id(user_id)
            
            return None
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            raise
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account."""
        try:
            object_id = ObjectId(user_id)
            collection = self._get_collection()
            result = await collection.update_one(
                {"_id": object_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"User deactivated: {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
            return False
    
    async def activate_user(self, user_id: str) -> bool:
        """Activate user account."""
        try:
            object_id = ObjectId(user_id)
            collection = self._get_collection()
            result = await collection.update_one(
                {"_id": object_id},
                {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"User activated: {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error activating user {user_id}: {e}")
            return False
    
    def user_to_response(self, user: UserInDB) -> User:
        """Convert UserInDB to User response model."""
        return User(
            id=str(user.id),
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at,
            is_active=user.is_active
        )


# Global user service instance
user_service = UserService()
