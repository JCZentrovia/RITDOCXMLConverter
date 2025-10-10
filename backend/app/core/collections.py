"""
MongoDB collections and indexes setup.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING
import logging

logger = logging.getLogger(__name__)


class Collections:
    """MongoDB collection names."""
    USERS = "users"
    MANUSCRIPTS = "manuscripts"
    CONVERSION_TASKS = "conversion_tasks"


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create database indexes for optimal performance."""
    
    try:
        # Users collection indexes
        users_indexes = [
            IndexModel([("email", ASCENDING)], unique=True, name="email_unique"),
            IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
            IndexModel([("is_active", ASCENDING)], name="is_active_asc")
        ]
        
        await db[Collections.USERS].create_indexes(users_indexes)
        logger.info("Created indexes for users collection")
        
        # Manuscripts collection indexes
        manuscripts_indexes = [
            IndexModel([("user_id", ASCENDING)], name="user_id_asc"),
            IndexModel([("status", ASCENDING)], name="status_asc"),
            IndexModel([("upload_date", DESCENDING)], name="upload_date_desc"),
            IndexModel([("user_id", ASCENDING), ("upload_date", DESCENDING)], name="user_upload_date"),
            IndexModel([("status", ASCENDING), ("processing_started_at", ASCENDING)], name="status_processing"),
            IndexModel([("pdf_s3_key", ASCENDING)], unique=True, name="pdf_s3_key_unique"),
            IndexModel([("docx_s3_key", ASCENDING)], sparse=True, name="docx_s3_key_sparse")
        ]
        
        await db[Collections.MANUSCRIPTS].create_indexes(manuscripts_indexes)
        logger.info("Created indexes for manuscripts collection")
        
        # Conversion tasks collection indexes
        conversion_tasks_indexes = [
            IndexModel([("manuscript_id", ASCENDING)], name="manuscript_id_asc"),
            IndexModel([("user_id", ASCENDING)], name="user_id_asc"),
            IndexModel([("status", ASCENDING)], name="status_asc"),
            IndexModel([("priority", DESCENDING), ("created_at", ASCENDING)], name="priority_created_at"),
            IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
            IndexModel([("locked_by", ASCENDING)], sparse=True, name="locked_by_sparse"),
            IndexModel([("lock_expires_at", ASCENDING)], sparse=True, name="lock_expires_at_sparse"),
            IndexModel([("processing_started_at", ASCENDING)], sparse=True, name="processing_started_at_sparse"),
            IndexModel([("processing_completed_at", ASCENDING)], sparse=True, name="processing_completed_at_sparse"),
            IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="user_status"),
            IndexModel([("status", ASCENDING), ("priority", DESCENDING)], name="status_priority")
        ]
        
        await db[Collections.CONVERSION_TASKS].create_indexes(conversion_tasks_indexes)
        logger.info("Created indexes for conversion_tasks collection")
        
    except Exception as e:
        logger.error(f"Failed to create database indexes: {e}")
        raise


async def setup_collections(db: AsyncIOMotorDatabase) -> None:
    """Setup collections and indexes."""
    logger.info("Setting up database collections and indexes...")
    
    # Create indexes
    await create_indexes(db)
    
    # Verify collections exist (they are created automatically when first document is inserted)
    collections = await db.list_collection_names()
    logger.info(f"Available collections: {collections}")
    
    logger.info("Database setup completed successfully")


def get_collection_name(collection: str) -> str:
    """Get collection name with validation."""
    if hasattr(Collections, collection.upper()):
        return getattr(Collections, collection.upper())
    else:
        raise ValueError(f"Unknown collection: {collection}")


# Collection validation schemas (for MongoDB schema validation)
USER_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["email", "password_hash", "created_at", "is_active"],
        "properties": {
            "email": {
                "bsonType": "string",
                "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                "description": "Valid email address"
            },
            "password_hash": {
                "bsonType": "string",
                "minLength": 1,
                "description": "Hashed password"
            },
            "created_at": {
                "bsonType": "date",
                "description": "User creation timestamp"
            },
            "updated_at": {
                "bsonType": ["date", "null"],
                "description": "Last update timestamp"
            },
            "is_active": {
                "bsonType": "bool",
                "description": "User active status"
            }
        }
    }
}

MANUSCRIPT_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "file_name", "status", "pdf_s3_key", "upload_date", "content_type"],
        "properties": {
            "user_id": {
                "bsonType": "objectId",
                "description": "Reference to user document"
            },
            "file_name": {
                "bsonType": "string",
                "minLength": 1,
                "maxLength": 255,
                "description": "Original file name"
            },
            "status": {
                "bsonType": "string",
                "enum": ["pending", "processing", "complete", "failed"],
                "description": "Processing status"
            },
            "pdf_s3_key": {
                "bsonType": "string",
                "minLength": 1,
                "description": "S3 key for PDF file"
            },
            "docx_s3_key": {
                "bsonType": ["string", "null"],
                "description": "S3 key for converted Word document"
            },
            "upload_date": {
                "bsonType": "date",
                "description": "Upload timestamp"
            },
            "processing_started_at": {
                "bsonType": ["date", "null"],
                "description": "Processing start timestamp"
            },
            "processing_completed_at": {
                "bsonType": ["date", "null"],
                "description": "Processing completion timestamp"
            },
            "error_message": {
                "bsonType": ["string", "null"],
                "description": "Error message if processing failed"
            },
            "retry_count": {
                "bsonType": "int",
                "minimum": 0,
                "description": "Number of processing retries"
            },
            "file_size": {
                "bsonType": ["int", "null"],
                "minimum": 0,
                "description": "File size in bytes"
            },
            "content_type": {
                "bsonType": "string",
                "description": "MIME type of the file"
            }
        }
    }
}

CONVERSION_TASKS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["manuscript_id", "user_id", "quality", "status", "created_at", "priority"],
        "properties": {
            "manuscript_id": {
                "bsonType": "string",
                "description": "ID of the manuscript to convert"
            },
            "user_id": {
                "bsonType": "string",
                "description": "ID of the user requesting conversion"
            },
            "quality": {
                "bsonType": "string",
                "enum": ["standard", "high"],
                "description": "Conversion quality"
            },
            "include_metadata": {
                "bsonType": "bool",
                "description": "Whether to include document metadata"
            },
            "priority": {
                "bsonType": "int",
                "minimum": 1,
                "maximum": 10,
                "description": "Conversion priority"
            },
            "status": {
                "bsonType": "string",
                "enum": ["pending", "processing", "completed", "failed", "cancelled"],
                "description": "Conversion status"
            },
            "progress_percentage": {
                "bsonType": "int",
                "minimum": 0,
                "maximum": 100,
                "description": "Conversion progress"
            },
            "created_at": {
                "bsonType": "date",
                "description": "Task creation timestamp"
            },
            "processing_started_at": {
                "bsonType": ["date", "null"],
                "description": "Processing start timestamp"
            },
            "processing_completed_at": {
                "bsonType": ["date", "null"],
                "description": "Processing completion timestamp"
            },
            "docx_s3_key": {
                "bsonType": ["string", "null"],
                "description": "S3 key of converted DOCX file"
            },
            "error_message": {
                "bsonType": ["string", "null"],
                "description": "Error message if conversion failed"
            },
            "conversion_metadata": {
                "bsonType": ["object", "null"],
                "description": "Conversion metadata and statistics"
            },
            "retry_count": {
                "bsonType": "int",
                "minimum": 0,
                "description": "Number of retry attempts"
            },
            "max_retries": {
                "bsonType": "int",
                "minimum": 0,
                "description": "Maximum retry attempts"
            },
            "scheduled_for": {
                "bsonType": ["date", "null"],
                "description": "Scheduled execution time"
            },
            "locked_by": {
                "bsonType": ["string", "null"],
                "description": "Worker ID that locked this task"
            },
            "locked_at": {
                "bsonType": ["date", "null"],
                "description": "Lock timestamp"
            },
            "lock_expires_at": {
                "bsonType": ["date", "null"],
                "description": "Lock expiration timestamp"
            }
        }
    }
}


async def create_collection_validation(db: AsyncIOMotorDatabase) -> None:
    """Create collection validation rules (optional - for data integrity)."""
    try:
        # Create users collection with validation
        await db.create_collection(
            Collections.USERS,
            validator=USER_SCHEMA
        )
        logger.info("Created users collection with validation")
        
        # Create manuscripts collection with validation  
        await db.create_collection(
            Collections.MANUSCRIPTS,
            validator=MANUSCRIPT_SCHEMA
        )
        logger.info("Created manuscripts collection with validation")
        
        # Create conversion tasks collection with validation
        await db.create_collection(
            Collections.CONVERSION_TASKS,
            validator=CONVERSION_TASKS_SCHEMA
        )
        logger.info("Created conversion_tasks collection with validation")
        
    except Exception as e:
        # Collections might already exist, which is fine
        logger.info(f"Collections already exist or validation setup skipped: {e}")
