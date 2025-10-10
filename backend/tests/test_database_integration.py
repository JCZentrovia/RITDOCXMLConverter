"""
Integration tests for database operations.

This module tests database connectivity, CRUD operations,
aggregation pipelines, and data consistency.
"""

import pytest
from datetime import datetime, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.collections import Collections
from app.models.user import UserCreate, UserInDB
from app.models.manuscript import ManuscriptCreate, ManuscriptInDB, ManuscriptStatus
from app.models.conversion import ConversionTaskCreate, ConversionTaskInDB, ConversionStatus, ConversionQuality
from app.services.user_service import user_service
from app.services.manuscript_service import manuscript_service
from app.services.conversion_service import conversion_service

pytestmark = [pytest.mark.asyncio, pytest.mark.integration, pytest.mark.database]

class TestDatabaseConnection:
    """Test database connection and basic operations."""
    
    async def test_database_connection(self, db: AsyncIOMotorDatabase):
        """Test database connection is working."""
        # Test ping
        result = await db.client.admin.command('ping')
        assert result['ok'] == 1
    
    async def test_database_collections(self, db: AsyncIOMotorDatabase):
        """Test database collections can be accessed."""
        # Test collection access
        users_collection = db[Collections.USERS]
        manuscripts_collection = db[Collections.MANUSCRIPTS]
        conversion_tasks_collection = db[Collections.CONVERSION_TASKS]
        
        # Test basic operations
        await users_collection.count_documents({})
        await manuscripts_collection.count_documents({})
        await conversion_tasks_collection.count_documents({})
    
    async def test_database_indexes(self, db: AsyncIOMotorDatabase):
        """Test database indexes are created properly."""
        # Check users collection indexes
        users_indexes = await db[Collections.USERS].list_indexes().to_list(length=None)
        index_names = [idx['name'] for idx in users_indexes]
        
        # Should have default _id index at minimum
        assert '_id_' in index_names
        
        # Check for email index (if implemented)
        email_indexes = [idx for idx in users_indexes if 'email' in str(idx.get('key', {}))]
        # Email index should exist for uniqueness
        assert len(email_indexes) > 0 or any('email' in str(idx.get('key', {})) for idx in users_indexes)

class TestUserDatabaseOperations:
    """Test user-related database operations."""
    
    async def test_create_user(self, db: AsyncIOMotorDatabase, test_data_factory):
        """Test user creation in database."""
        user_data = test_data_factory.user_create_data()
        
        # Create user
        user = await user_service.create_user(user_data)
        
        # Verify user was created
        assert user.id is not None
        assert user.email == user_data.email
        assert user.full_name == user_data.full_name
        assert user.is_active is True
        assert user.created_at is not None
        
        # Verify in database
        db_user = await db[Collections.USERS].find_one({"_id": ObjectId(user.id)})
        assert db_user is not None
        assert db_user["email"] == user_data.email
    
    async def test_get_user_by_email(self, db: AsyncIOMotorDatabase, test_user: UserInDB):
        """Test retrieving user by email."""
        user = await user_service.get_user_by_email(test_user.email)
        
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email
        assert user.full_name == test_user.full_name
    
    async def test_get_user_by_id(self, db: AsyncIOMotorDatabase, test_user: UserInDB):
        """Test retrieving user by ID."""
        user = await user_service.get_user_by_id(test_user.id)
        
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email
        assert user.full_name == test_user.full_name
    
    async def test_update_user(self, db: AsyncIOMotorDatabase, test_user: UserInDB):
        """Test updating user information."""
        new_name = "Updated Name"
        
        updated_user = await user_service.update_user(test_user.id, {"full_name": new_name})
        
        assert updated_user is not None
        assert updated_user.full_name == new_name
        assert updated_user.email == test_user.email  # Should remain unchanged
        
        # Verify in database
        db_user = await db[Collections.USERS].find_one({"_id": ObjectId(test_user.id)})
        assert db_user["full_name"] == new_name
    
    async def test_user_email_uniqueness(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test that email uniqueness is enforced."""
        # Try to create user with same email
        duplicate_user_data = test_data_factory.user_create_data(email=test_user.email)
        
        with pytest.raises(Exception):  # Should raise some form of exception
            await user_service.create_user(duplicate_user_data)
    
    async def test_delete_user(self, db: AsyncIOMotorDatabase, test_data_factory):
        """Test user deletion."""
        # Create a user to delete
        user_data = test_data_factory.user_create_data()
        user = await user_service.create_user(user_data)
        
        # Delete user
        deleted = await user_service.delete_user(user.id)
        assert deleted is True
        
        # Verify user is deleted
        db_user = await db[Collections.USERS].find_one({"_id": ObjectId(user.id)})
        assert db_user is None
        
        # Verify get_user_by_id returns None
        retrieved_user = await user_service.get_user_by_id(user.id)
        assert retrieved_user is None

class TestManuscriptDatabaseOperations:
    """Test manuscript-related database operations."""
    
    async def test_create_manuscript(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test manuscript creation in database."""
        manuscript_data = test_data_factory.manuscript_create_data()
        
        # Create manuscript
        manuscript = await manuscript_service.create_manuscript(manuscript_data, test_user.id)
        
        # Verify manuscript was created
        assert manuscript.id is not None
        assert manuscript.file_name == manuscript_data.file_name
        assert manuscript.user_id == test_user.id
        assert manuscript.status == ManuscriptStatus.UPLOADED
        assert manuscript.created_at is not None
        
        # Verify in database
        db_manuscript = await db[Collections.MANUSCRIPTS].find_one({"_id": ObjectId(manuscript.id)})
        assert db_manuscript is not None
        assert db_manuscript["file_name"] == manuscript_data.file_name
        assert db_manuscript["user_id"] == test_user.id
    
    async def test_get_manuscript_by_id(self, db: AsyncIOMotorDatabase, test_manuscript: ManuscriptInDB):
        """Test retrieving manuscript by ID."""
        manuscript = await manuscript_service.get_manuscript_by_id(test_manuscript.id, test_manuscript.user_id)
        
        assert manuscript is not None
        assert manuscript.id == test_manuscript.id
        assert manuscript.file_name == test_manuscript.file_name
        assert manuscript.user_id == test_manuscript.user_id
    
    async def test_get_manuscripts_by_user(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_manuscript: ManuscriptInDB):
        """Test retrieving manuscripts by user."""
        manuscripts = await manuscript_service.get_manuscripts_by_user(test_user.id)
        
        assert len(manuscripts) >= 1
        manuscript_ids = [m.id for m in manuscripts]
        assert test_manuscript.id in manuscript_ids
    
    async def test_update_manuscript(self, db: AsyncIOMotorDatabase, test_manuscript: ManuscriptInDB):
        """Test updating manuscript."""
        new_status = ManuscriptStatus.PROCESSING
        
        updated_manuscript = await manuscript_service.update_manuscript(
            test_manuscript.id, 
            {"status": new_status}
        )
        
        assert updated_manuscript is not None
        assert updated_manuscript.status == new_status
        
        # Verify in database
        db_manuscript = await db[Collections.MANUSCRIPTS].find_one({"_id": ObjectId(test_manuscript.id)})
        assert db_manuscript["status"] == new_status.value
    
    async def test_delete_manuscript(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test manuscript deletion."""
        # Create a manuscript to delete
        manuscript_data = test_data_factory.manuscript_create_data()
        manuscript = await manuscript_service.create_manuscript(manuscript_data, test_user.id)
        
        # Delete manuscript
        deleted = await manuscript_service.delete_manuscript(manuscript.id, test_user.id)
        assert deleted is True
        
        # Verify manuscript is deleted
        db_manuscript = await db[Collections.MANUSCRIPTS].find_one({"_id": ObjectId(manuscript.id)})
        assert db_manuscript is None
    
    async def test_manuscript_pagination(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test manuscript pagination."""
        # Create multiple manuscripts
        manuscripts = []
        for i in range(5):
            manuscript_data = test_data_factory.manuscript_create_data()
            manuscript = await manuscript_service.create_manuscript(manuscript_data, test_user.id)
            manuscripts.append(manuscript)
        
        # Test pagination
        page_1 = await manuscript_service.get_manuscripts_by_user(test_user.id, page=1, size=2)
        page_2 = await manuscript_service.get_manuscripts_by_user(test_user.id, page=2, size=2)
        
        assert len(page_1) == 2
        assert len(page_2) <= 2
        
        # Ensure different manuscripts on different pages
        page_1_ids = [m.id for m in page_1]
        page_2_ids = [m.id for m in page_2]
        assert not set(page_1_ids).intersection(set(page_2_ids))

class TestConversionTaskDatabaseOperations:
    """Test conversion task-related database operations."""
    
    async def test_create_conversion_task(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_manuscript: ManuscriptInDB):
        """Test conversion task creation."""
        task_data = ConversionTaskCreate(
            manuscript_id=test_manuscript.id,
            quality=ConversionQuality.STANDARD,
            include_metadata=True,
            priority=5
        )
        
        # Create conversion task
        task = await conversion_service.create_conversion_task(task_data, test_user.id)
        
        # Verify task was created
        assert task.id is not None
        assert task.manuscript_id == test_manuscript.id
        assert task.user_id == test_user.id
        assert task.status == ConversionStatus.PENDING
        assert task.quality == ConversionQuality.STANDARD
        assert task.created_at is not None
        
        # Verify in database
        db_task = await db[Collections.CONVERSION_TASKS].find_one({"_id": ObjectId(task.id)})
        assert db_task is not None
        assert db_task["manuscript_id"] == test_manuscript.id
        assert db_task["user_id"] == test_user.id
    
    async def test_get_conversion_task_by_id(self, db: AsyncIOMotorDatabase, test_conversion_task: ConversionTaskInDB):
        """Test retrieving conversion task by ID."""
        task = await conversion_service.get_conversion_task(test_conversion_task.id, test_conversion_task.user_id)
        
        assert task is not None
        assert task.id == test_conversion_task.id
        assert task.manuscript_id == test_conversion_task.manuscript_id
        assert task.user_id == test_conversion_task.user_id
    
    async def test_update_conversion_task(self, db: AsyncIOMotorDatabase, test_conversion_task: ConversionTaskInDB):
        """Test updating conversion task."""
        from app.models.conversion import ConversionTaskUpdate
        
        update_data = ConversionTaskUpdate(
            status=ConversionStatus.PROCESSING,
            progress_percentage=50,
            processing_started_at=datetime.utcnow()
        )
        
        updated_task = await conversion_service.update_conversion_task(test_conversion_task.id, update_data)
        
        assert updated_task is not None
        assert updated_task.status == ConversionStatus.PROCESSING
        assert updated_task.progress_percentage == 50
        assert updated_task.processing_started_at is not None
        
        # Verify in database
        db_task = await db[Collections.CONVERSION_TASKS].find_one({"_id": ObjectId(test_conversion_task.id)})
        assert db_task["status"] == ConversionStatus.PROCESSING.value
        assert db_task["progress_percentage"] == 50
    
    async def test_get_pending_conversion_tasks(self, db: AsyncIOMotorDatabase, test_conversion_task: ConversionTaskInDB):
        """Test retrieving pending conversion tasks."""
        pending_tasks = await conversion_service.get_pending_conversion_tasks(limit=10)
        
        assert len(pending_tasks) >= 1
        task_ids = [t.id for t in pending_tasks]
        assert test_conversion_task.id in task_ids
        
        # All tasks should be pending
        for task in pending_tasks:
            assert task.status == ConversionStatus.PENDING

class TestDatabaseAggregations:
    """Test database aggregation operations."""
    
    async def test_manuscript_status_aggregation(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test manuscript status aggregation."""
        # Create manuscripts with different statuses
        statuses = [ManuscriptStatus.UPLOADED, ManuscriptStatus.PROCESSING, ManuscriptStatus.COMPLETE]
        
        for status in statuses:
            manuscript_data = test_data_factory.manuscript_create_data()
            manuscript = await manuscript_service.create_manuscript(manuscript_data, test_user.id)
            await manuscript_service.update_manuscript(manuscript.id, {"status": status})
        
        # Aggregate by status
        pipeline = [
            {"$match": {"user_id": test_user.id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        results = await db[Collections.MANUSCRIPTS].aggregate(pipeline).to_list(length=None)
        
        # Should have results for each status
        status_counts = {result["_id"]: result["count"] for result in results}
        
        for status in statuses:
            assert status.value in status_counts
            assert status_counts[status.value] >= 1
    
    async def test_conversion_task_priority_aggregation(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_manuscript: ManuscriptInDB):
        """Test conversion task priority aggregation."""
        # Create tasks with different priorities
        priorities = [1, 5, 10]
        
        for priority in priorities:
            task_data = ConversionTaskCreate(
                manuscript_id=test_manuscript.id,
                quality=ConversionQuality.STANDARD,
                include_metadata=True,
                priority=priority
            )
            await conversion_service.create_conversion_task(task_data, test_user.id)
        
        # Aggregate by priority
        pipeline = [
            {"$match": {"user_id": test_user.id}},
            {"$group": {
                "_id": "$priority",
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        results = await db[Collections.CONVERSION_TASKS].aggregate(pipeline).to_list(length=None)
        
        # Should have results for each priority
        priority_counts = {result["_id"]: result["count"] for result in results}
        
        for priority in priorities:
            assert priority in priority_counts
            assert priority_counts[priority] >= 1
    
    async def test_user_manuscript_count_aggregation(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test user manuscript count aggregation."""
        # Create multiple manuscripts for user
        manuscript_count = 3
        for i in range(manuscript_count):
            manuscript_data = test_data_factory.manuscript_create_data()
            await manuscript_service.create_manuscript(manuscript_data, test_user.id)
        
        # Aggregate manuscript count by user
        pipeline = [
            {"$group": {
                "_id": "$user_id",
                "manuscript_count": {"$sum": 1}
            }},
            {"$match": {"_id": test_user.id}}
        ]
        
        results = await db[Collections.MANUSCRIPTS].aggregate(pipeline).to_list(length=None)
        
        assert len(results) == 1
        assert results[0]["_id"] == test_user.id
        assert results[0]["manuscript_count"] >= manuscript_count

class TestDatabaseTransactions:
    """Test database transaction operations."""
    
    async def test_manuscript_conversion_transaction(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test transactional operations between manuscripts and conversion tasks."""
        manuscript_data = test_data_factory.manuscript_create_data()
        
        # This would be a transaction in a real implementation
        # For now, test that both operations succeed or fail together
        
        # Create manuscript
        manuscript = await manuscript_service.create_manuscript(manuscript_data, test_user.id)
        
        try:
            # Create conversion task
            task_data = ConversionTaskCreate(
                manuscript_id=manuscript.id,
                quality=ConversionQuality.STANDARD,
                include_metadata=True,
                priority=5
            )
            task = await conversion_service.create_conversion_task(task_data, test_user.id)
            
            # Both should exist
            assert manuscript.id is not None
            assert task.id is not None
            
            # Verify both exist in database
            db_manuscript = await db[Collections.MANUSCRIPTS].find_one({"_id": ObjectId(manuscript.id)})
            db_task = await db[Collections.CONVERSION_TASKS].find_one({"_id": ObjectId(task.id)})
            
            assert db_manuscript is not None
            assert db_task is not None
            
        except Exception as e:
            # If task creation fails, manuscript should still exist (no transaction rollback in this simple case)
            # In a real implementation, you might want to clean up the manuscript
            pytest.fail(f"Transaction test failed: {e}")

class TestDatabasePerformance:
    """Test database performance and optimization."""
    
    async def test_large_dataset_query_performance(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test query performance with larger datasets."""
        import time
        
        # Create a moderate number of manuscripts for performance testing
        manuscript_count = 50
        manuscripts = []
        
        start_time = time.time()
        
        for i in range(manuscript_count):
            manuscript_data = test_data_factory.manuscript_create_data()
            manuscript = await manuscript_service.create_manuscript(manuscript_data, test_user.id)
            manuscripts.append(manuscript)
        
        creation_time = time.time() - start_time
        
        # Test query performance
        start_time = time.time()
        retrieved_manuscripts = await manuscript_service.get_manuscripts_by_user(test_user.id)
        query_time = time.time() - start_time
        
        # Verify results
        assert len(retrieved_manuscripts) >= manuscript_count
        
        # Performance assertions (adjust thresholds as needed)
        assert creation_time < 30.0, f"Creation took too long: {creation_time}s"
        assert query_time < 5.0, f"Query took too long: {query_time}s"
    
    async def test_concurrent_operations(self, db: AsyncIOMotorDatabase, test_user: UserInDB, test_data_factory):
        """Test concurrent database operations."""
        import asyncio
        
        async def create_manuscript():
            manuscript_data = test_data_factory.manuscript_create_data()
            return await manuscript_service.create_manuscript(manuscript_data, test_user.id)
        
        # Run concurrent operations
        tasks = [create_manuscript() for _ in range(10)]
        manuscripts = await asyncio.gather(*tasks)
        
        # Verify all operations succeeded
        assert len(manuscripts) == 10
        
        # Verify all manuscripts have unique IDs
        manuscript_ids = [m.id for m in manuscripts]
        assert len(set(manuscript_ids)) == 10  # All unique
