"""
Database connection and configuration.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings


class Database:
    """Database connection manager."""
    
    client: AsyncIOMotorClient = None
    database: AsyncIOMotorDatabase = None


db = Database()


async def connect_to_mongo():
    """Create database connection."""
    print(f"Connecting to MongoDB at {settings.mongodb_url}")
    db.client = AsyncIOMotorClient(settings.mongodb_url)
    db.database = db.client[settings.mongodb_database]
    
    # Test the connection
    try:
        await db.client.admin.command('ping')
        print("Connected to MongoDB Atlas successfully")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close database connection."""
    print("Closing MongoDB connection")
    if db.client:
        db.client.close()
    print("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance."""
    return db.database
