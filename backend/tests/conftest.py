"""
Test configuration and fixtures for the manuscript processor backend.

This module provides comprehensive test fixtures, database setup,
authentication helpers, and testing utilities.
"""

import asyncio
import os
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
import tempfile
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from faker import Faker

# Import application components
from app.main import app
from app.core.config import settings
from app.core.database import get_database
from app.core.security import create_access_token, get_password_hash
from app.models.user import UserCreate, UserInDB
from app.models.manuscript import ManuscriptCreate, ManuscriptInDB, ManuscriptStatus
from app.models.conversion import ConversionTaskCreate, ConversionTaskInDB, ConversionStatus, ConversionQuality
from app.services.user_service import user_service
from app.services.manuscript_service import manuscript_service
from app.services.conversion_service import conversion_service
from app.services.s3_service import s3_service

# Initialize faker for test data generation
fake = Faker()

# Test database configuration
TEST_DATABASE_URL = "mongodb://localhost:27017"
TEST_DATABASE_NAME = "manuscript_processor_test"

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def test_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Create test database connection."""
    client = AsyncIOMotorClient(TEST_DATABASE_URL)
    db = client[TEST_DATABASE_NAME]
    
    # Clear test database before tests
    await client.drop_database(TEST_DATABASE_NAME)
    
    yield db
    
    # Clean up after tests
    await client.drop_database(TEST_DATABASE_NAME)
    client.close()

@pytest_asyncio.fixture
async def db(test_db: AsyncIOMotorDatabase) -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Provide clean database for each test."""
    # Clear all collections before each test
    collections = await test_db.list_collection_names()
    for collection_name in collections:
        await test_db[collection_name].delete_many({})
    
    yield test_db

@pytest.fixture
def override_get_database(db: AsyncIOMotorDatabase):
    """Override database dependency for testing."""
    def _override_get_database():
        return db
    
    app.dependency_overrides[get_database] = _override_get_database
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client(override_get_database) -> TestClient:
    """Create test client."""
    return TestClient(app)

@pytest_asyncio.fixture
async def async_client(override_get_database) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

@pytest_asyncio.fixture
async def test_user(db: AsyncIOMotorDatabase) -> UserInDB:
    """Create test user."""
    user_data = UserCreate(
        email="test@example.com",
        password="testpassword123",
        full_name="Test User"
    )
    
    user = await user_service.create_user(user_data)
    return user

@pytest_asyncio.fixture
async def admin_user(db: AsyncIOMotorDatabase) -> UserInDB:
    """Create admin test user."""
    user_data = UserCreate(
        email="admin@example.com",
        password="adminpassword123",
        full_name="Admin User"
    )
    
    user = await user_service.create_user(user_data)
    # Update user to admin (if role system is implemented)
    # await user_service.update_user_role(user.id, "admin")
    return user

@pytest.fixture
def auth_headers(test_user: UserInDB) -> Dict[str, str]:
    """Create authentication headers for test user."""
    access_token = create_access_token(
        data={"sub": test_user.email, "user_id": str(test_user.id)}
    )
    return {"Authorization": f"Bearer {access_token}"}

@pytest.fixture
def admin_auth_headers(admin_user: UserInDB) -> Dict[str, str]:
    """Create authentication headers for admin user."""
    access_token = create_access_token(
        data={"sub": admin_user.email, "user_id": str(admin_user.id)}
    )
    return {"Authorization": f"Bearer {access_token}"}

@pytest_asyncio.fixture
async def test_manuscript(db: AsyncIOMotorDatabase, test_user: UserInDB) -> ManuscriptInDB:
    """Create test manuscript."""
    manuscript_data = ManuscriptCreate(
        file_name="test_document.pdf",
        original_name="Test Document.pdf",
        file_size=1024000,  # 1MB
        content_type="application/pdf",
        pdf_s3_key="test-pdfs/test_document.pdf"
    )
    
    manuscript = await manuscript_service.create_manuscript(manuscript_data, test_user.id)
    return manuscript

@pytest_asyncio.fixture
async def test_conversion_task(
    db: AsyncIOMotorDatabase, 
    test_user: UserInDB, 
    test_manuscript: ManuscriptInDB
) -> ConversionTaskInDB:
    """Create test conversion task."""
    task_data = ConversionTaskCreate(
        manuscript_id=test_manuscript.id,
        quality=ConversionQuality.STANDARD,
        include_metadata=True,
        priority=5
    )
    
    task = await conversion_service.create_conversion_task(task_data, test_user.id)
    return task

@pytest.fixture
def mock_s3_service():
    """Mock S3 service for testing."""
    mock_service = MagicMock()
    mock_service.generate_presigned_upload_url = AsyncMock(return_value={
        "upload_url": "https://test-bucket.s3.amazonaws.com/test-key",
        "fields": {"key": "test-key", "AWSAccessKeyId": "test-key-id"},
        "s3_key": "test-key"
    })
    mock_service.generate_presigned_download_url = AsyncMock(
        return_value="https://test-bucket.s3.amazonaws.com/test-key?signature=test"
    )
    mock_service.check_bucket_access = MagicMock(return_value=True)
    mock_service.get_file_metadata = AsyncMock(return_value={
        "size": 1024000,
        "last_modified": datetime.utcnow(),
        "content_type": "application/pdf"
    })
    mock_service.delete_file = AsyncMock(return_value=True)
    
    return mock_service

@pytest.fixture
def temp_directory():
    """Create temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_pdf_file(temp_directory: Path) -> Path:
    """Create sample PDF file for testing."""
    pdf_path = temp_directory / "sample.pdf"
    
    # Create a minimal PDF file for testing
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Hello World) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000189 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
284
%%EOF"""
    
    pdf_path.write_bytes(pdf_content)
    return pdf_path

@pytest.fixture
def test_data_factory():
    """Factory for generating test data."""
    class TestDataFactory:
        @staticmethod
        def user_create_data(**kwargs) -> UserCreate:
            """Generate UserCreate test data."""
            defaults = {
                "email": fake.email(),
                "password": fake.password(length=12),
                "full_name": fake.name()
            }
            defaults.update(kwargs)
            return UserCreate(**defaults)
        
        @staticmethod
        def manuscript_create_data(**kwargs) -> ManuscriptCreate:
            """Generate ManuscriptCreate test data."""
            defaults = {
                "file_name": f"{fake.slug()}.pdf",
                "original_name": f"{fake.catch_phrase()}.pdf",
                "file_size": fake.random_int(min=100000, max=10000000),
                "content_type": "application/pdf",
                "pdf_s3_key": f"test-pdfs/{fake.uuid4()}.pdf"
            }
            defaults.update(kwargs)
            return ManuscriptCreate(**defaults)
        
        @staticmethod
        def conversion_task_create_data(**kwargs) -> ConversionTaskCreate:
            """Generate ConversionTaskCreate test data."""
            defaults = {
                "manuscript_id": fake.uuid4(),
                "quality": fake.random_element(elements=list(ConversionQuality)),
                "include_metadata": fake.boolean(),
                "priority": fake.random_int(min=1, max=10)
            }
            defaults.update(kwargs)
            return ConversionTaskCreate(**defaults)
    
    return TestDataFactory()

@pytest.fixture
def mock_conversion_service():
    """Mock conversion service for testing."""
    mock_service = MagicMock()
    mock_service.convert_pdf_to_docx = AsyncMock(return_value=(
        "test-docx/converted_document.docx",
        {
            "conversion_duration_seconds": 15.5,
            "pdf_info": {
                "pages": 10,
                "size_mb": 2.5
            },
            "conversion_stats": {
                "output_size_mb": 1.8,
                "quality": "standard"
            }
        }
    ))
    mock_service.get_conversion_capabilities = AsyncMock(return_value={
        "temp_directory": "/tmp/test",
        "thread_pool_workers": 4,
        "supported_input_formats": ["pdf"],
        "supported_output_formats": ["docx"]
    })
    
    return mock_service

@pytest.fixture
def mock_scheduler_monitor():
    """Mock scheduler monitor for testing."""
    mock_monitor = MagicMock()
    mock_monitor.get_health_status = MagicMock(return_value={
        "status": "running",
        "health_status": "healthy",
        "health_issues": [],
        "uptime_seconds": 3600,
        "current_execution": None,
        "metrics": {
            "total_executions": 10,
            "successful_executions": 9,
            "failed_executions": 1,
            "success_rate_percentage": 90.0
        }
    })
    mock_monitor.start_execution = MagicMock()
    mock_monitor.end_execution = MagicMock()
    mock_monitor.get_execution_history = MagicMock(return_value=[])
    mock_monitor.get_performance_trends = MagicMock(return_value={
        "time_period_hours": 24,
        "executions_count": 10,
        "trends": []
    })
    
    return mock_monitor

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables."""
    # Store original values
    original_env = {}
    test_env_vars = {
        "TESTING": "true",
        "DATABASE_URL": TEST_DATABASE_URL,
        "DATABASE_NAME": TEST_DATABASE_NAME,
        "JWT_SECRET_KEY": "test-secret-key-for-testing-only",
        "S3_BUCKET_NAME": "test-manuscript-bucket",
        "AWS_REGION": "us-east-1",
        "DEBUG": "true"
    }
    
    # Set test environment variables
    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield
    
    # Restore original environment variables
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    mock_service = MagicMock()
    mock_service.send_password_reset_email = AsyncMock(return_value=True)
    mock_service.send_welcome_email = AsyncMock(return_value=True)
    mock_service.send_conversion_complete_email = AsyncMock(return_value=True)
    
    return mock_service

# Test utilities
class TestUtils:
    """Utility functions for testing."""
    
    @staticmethod
    def assert_datetime_close(dt1: datetime, dt2: datetime, delta_seconds: int = 5):
        """Assert that two datetimes are close within delta_seconds."""
        diff = abs((dt1 - dt2).total_seconds())
        assert diff <= delta_seconds, f"Datetimes differ by {diff} seconds, expected <= {delta_seconds}"
    
    @staticmethod
    def assert_valid_uuid(uuid_string: str):
        """Assert that string is a valid UUID."""
        import uuid
        try:
            uuid.UUID(uuid_string)
        except ValueError:
            pytest.fail(f"'{uuid_string}' is not a valid UUID")
    
    @staticmethod
    def assert_valid_email(email: str):
        """Assert that string is a valid email."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        assert re.match(email_pattern, email), f"'{email}' is not a valid email"
    
    @staticmethod
    def create_mock_file_upload(filename: str, content: bytes, content_type: str = "application/pdf"):
        """Create mock file upload for testing."""
        from io import BytesIO
        return {
            "file": BytesIO(content),
            "filename": filename,
            "content_type": content_type
        }

@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtils()
