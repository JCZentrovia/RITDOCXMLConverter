"""
Unit tests for manuscript API endpoints.

This module tests manuscript upload, listing, retrieval, conversion,
and download functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from httpx import AsyncClient
from bson import ObjectId

from app.models.manuscript import ManuscriptStatus
from app.models.conversion import ConversionStatus, ConversionQuality
from app.services.manuscript_service import manuscript_service
from app.services.conversion_service import conversion_service

pytestmark = pytest.mark.asyncio

class TestManuscriptUpload:
    """Test manuscript upload endpoints."""
    
    @patch('app.services.s3_service.s3_service')
    async def test_get_upload_url_success(self, mock_s3, async_client: AsyncClient, auth_headers: dict):
        """Test successful upload URL generation."""
        mock_s3.generate_presigned_upload_url.return_value = {
            "upload_url": "https://test-bucket.s3.amazonaws.com/test-key",
            "fields": {"key": "test-key", "AWSAccessKeyId": "test-key-id"},
            "s3_key": "test-key"
        }
        
        response = await async_client.post(
            "/api/v1/manuscripts/upload-url",
            json={
                "filename": "test_document.pdf",
                "content_type": "application/pdf",
                "file_size": 1024000
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "upload_url" in data["data"]
        assert "fields" in data["data"]
        assert "s3_key" in data["data"]
        
        mock_s3.generate_presigned_upload_url.assert_called_once()
    
    async def test_get_upload_url_invalid_file_type(self, async_client: AsyncClient, auth_headers: dict):
        """Test upload URL generation with invalid file type."""
        response = await async_client.post(
            "/api/v1/manuscripts/upload-url",
            json={
                "filename": "test_document.txt",
                "content_type": "text/plain",
                "file_size": 1024000
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert "file type" in data["detail"].lower()
    
    async def test_get_upload_url_file_too_large(self, async_client: AsyncClient, auth_headers: dict):
        """Test upload URL generation with file too large."""
        response = await async_client.post(
            "/api/v1/manuscripts/upload-url",
            json={
                "filename": "test_document.pdf",
                "content_type": "application/pdf",
                "file_size": 100 * 1024 * 1024  # 100MB (assuming limit is lower)
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert "file size" in data["detail"].lower()
    
    async def test_get_upload_url_no_auth(self, async_client: AsyncClient):
        """Test upload URL generation without authentication."""
        response = await async_client.post(
            "/api/v1/manuscripts/upload-url",
            json={
                "filename": "test_document.pdf",
                "content_type": "application/pdf",
                "file_size": 1024000
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_confirm_upload_success(self, async_client: AsyncClient, auth_headers: dict, test_user):
        """Test successful upload confirmation."""
        response = await async_client.post(
            "/api/v1/manuscripts/confirm-upload",
            json={
                "s3_key": "test-pdfs/test_document.pdf",
                "filename": "test_document.pdf",
                "original_name": "Test Document.pdf",
                "file_size": 1024000,
                "content_type": "application/pdf"
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        manuscript = data["data"]
        assert manuscript["file_name"] == "test_document.pdf"
        assert manuscript["original_name"] == "Test Document.pdf"
        assert manuscript["file_size"] == 1024000
        assert manuscript["status"] == ManuscriptStatus.UPLOADED.value
        assert manuscript["user_id"] == str(test_user.id)
    
    async def test_confirm_upload_invalid_s3_key(self, async_client: AsyncClient, auth_headers: dict):
        """Test upload confirmation with invalid S3 key."""
        response = await async_client.post(
            "/api/v1/manuscripts/confirm-upload",
            json={
                "s3_key": "",  # Empty S3 key
                "filename": "test_document.pdf",
                "original_name": "Test Document.pdf",
                "file_size": 1024000,
                "content_type": "application/pdf"
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestManuscriptListing:
    """Test manuscript listing endpoints."""
    
    async def test_list_manuscripts_success(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test successful manuscript listing."""
        response = await async_client.get(
            "/api/v1/manuscripts/",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "manuscripts" in data["data"]
        assert "pagination" in data["data"]
        
        manuscripts = data["data"]["manuscripts"]
        assert len(manuscripts) >= 1
        
        manuscript = manuscripts[0]
        assert manuscript["id"] == str(test_manuscript.id)
        assert manuscript["file_name"] == test_manuscript.file_name
        assert manuscript["status"] == test_manuscript.status.value
    
    async def test_list_manuscripts_with_pagination(self, async_client: AsyncClient, auth_headers: dict):
        """Test manuscript listing with pagination."""
        response = await async_client.get(
            "/api/v1/manuscripts/?page=1&size=5",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        pagination = data["data"]["pagination"]
        assert pagination["page"] == 1
        assert pagination["size"] == 5
        assert "total" in pagination
        assert "pages" in pagination
    
    async def test_list_manuscripts_with_status_filter(self, async_client: AsyncClient, auth_headers: dict):
        """Test manuscript listing with status filter."""
        response = await async_client.get(
            "/api/v1/manuscripts/?status=uploaded",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        manuscripts = data["data"]["manuscripts"]
        
        # All manuscripts should have the filtered status
        for manuscript in manuscripts:
            assert manuscript["status"] == "uploaded"
    
    async def test_list_manuscripts_with_search(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test manuscript listing with search."""
        response = await async_client.get(
            f"/api/v1/manuscripts/?search={test_manuscript.file_name[:5]}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        manuscripts = data["data"]["manuscripts"]
        
        # Should find the test manuscript
        manuscript_ids = [m["id"] for m in manuscripts]
        assert str(test_manuscript.id) in manuscript_ids
    
    async def test_list_manuscripts_no_auth(self, async_client: AsyncClient):
        """Test manuscript listing without authentication."""
        response = await async_client.get("/api/v1/manuscripts/")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

class TestManuscriptRetrieval:
    """Test manuscript retrieval endpoints."""
    
    async def test_get_manuscript_success(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test successful manuscript retrieval."""
        response = await async_client.get(
            f"/api/v1/manuscripts/{test_manuscript.id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        manuscript = data["data"]
        assert manuscript["id"] == str(test_manuscript.id)
        assert manuscript["file_name"] == test_manuscript.file_name
        assert manuscript["original_name"] == test_manuscript.original_name
        assert manuscript["status"] == test_manuscript.status.value
    
    async def test_get_manuscript_not_found(self, async_client: AsyncClient, auth_headers: dict):
        """Test manuscript retrieval with invalid ID."""
        fake_id = str(ObjectId())
        
        response = await async_client.get(
            f"/api/v1/manuscripts/{fake_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["success"] is False
    
    async def test_get_manuscript_invalid_id(self, async_client: AsyncClient, auth_headers: dict):
        """Test manuscript retrieval with malformed ID."""
        response = await async_client.get(
            "/api/v1/manuscripts/invalid_id",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_get_manuscript_no_auth(self, async_client: AsyncClient, test_manuscript):
        """Test manuscript retrieval without authentication."""
        response = await async_client.get(f"/api/v1/manuscripts/{test_manuscript.id}")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

class TestManuscriptConversion:
    """Test manuscript conversion endpoints."""
    
    async def test_start_conversion_success(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test successful conversion start."""
        response = await async_client.post(
            f"/api/v1/manuscripts/{test_manuscript.id}/convert",
            json={
                "quality": "standard",
                "include_metadata": True,
                "priority": 5
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        task = data["data"]
        assert task["manuscript_id"] == str(test_manuscript.id)
        assert task["quality"] == "standard"
        assert task["include_metadata"] is True
        assert task["priority"] == 5
        assert task["status"] == ConversionStatus.PENDING.value
    
    async def test_start_conversion_already_processing(self, async_client: AsyncClient, auth_headers: dict, test_manuscript, test_conversion_task):
        """Test conversion start when already processing."""
        response = await async_client.post(
            f"/api/v1/manuscripts/{test_manuscript.id}/convert",
            json={
                "quality": "high",
                "include_metadata": False,
                "priority": 3
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert "already" in data["detail"].lower()
    
    async def test_start_conversion_invalid_quality(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test conversion start with invalid quality."""
        response = await async_client.post(
            f"/api/v1/manuscripts/{test_manuscript.id}/convert",
            json={
                "quality": "invalid_quality",
                "include_metadata": True,
                "priority": 5
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_get_conversion_status_success(self, async_client: AsyncClient, auth_headers: dict, test_conversion_task):
        """Test successful conversion status retrieval."""
        response = await async_client.get(
            f"/api/v1/manuscripts/{test_conversion_task.manuscript_id}/conversion-status",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        task = data["data"]
        assert task["id"] == str(test_conversion_task.id)
        assert task["manuscript_id"] == str(test_conversion_task.manuscript_id)
        assert task["status"] == test_conversion_task.status.value
    
    async def test_get_conversion_status_no_task(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test conversion status when no task exists."""
        response = await async_client.get(
            f"/api/v1/manuscripts/{test_manuscript.id}/conversion-status",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["success"] is False

class TestManuscriptDownload:
    """Test manuscript download endpoints."""
    
    @patch('app.services.s3_service.s3_service')
    async def test_download_pdf_success(self, mock_s3, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test successful PDF download."""
        mock_s3.generate_presigned_download_url.return_value = "https://test-bucket.s3.amazonaws.com/download-url"
        
        response = await async_client.get(
            f"/api/v1/manuscripts/{test_manuscript.id}/download/pdf",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "download_url" in data["data"]
        assert "expires_in" in data["data"]
        
        mock_s3.generate_presigned_download_url.assert_called_once()
    
    @patch('app.services.s3_service.s3_service')
    async def test_download_docx_success(self, mock_s3, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test successful DOCX download."""
        # Update manuscript to have DOCX file
        await manuscript_service.update_manuscript(
            test_manuscript.id,
            {"docx_s3_key": "test-docx/converted_document.docx", "status": ManuscriptStatus.COMPLETE}
        )
        
        mock_s3.generate_presigned_download_url.return_value = "https://test-bucket.s3.amazonaws.com/download-url"
        
        response = await async_client.get(
            f"/api/v1/manuscripts/{test_manuscript.id}/download/docx",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "download_url" in data["data"]
        
        mock_s3.generate_presigned_download_url.assert_called_once()
    
    async def test_download_docx_not_available(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test DOCX download when not available."""
        response = await async_client.get(
            f"/api/v1/manuscripts/{test_manuscript.id}/download/docx",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert "not available" in data["detail"].lower()
    
    async def test_download_manuscript_not_found(self, async_client: AsyncClient, auth_headers: dict):
        """Test download for non-existent manuscript."""
        fake_id = str(ObjectId())
        
        response = await async_client.get(
            f"/api/v1/manuscripts/{fake_id}/download/pdf",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["success"] is False

class TestManuscriptDeletion:
    """Test manuscript deletion endpoints."""
    
    @patch('app.services.s3_service.s3_service')
    async def test_delete_manuscript_success(self, mock_s3, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test successful manuscript deletion."""
        mock_s3.delete_file.return_value = True
        
        response = await async_client.delete(
            f"/api/v1/manuscripts/{test_manuscript.id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
        
        # Verify manuscript is deleted
        deleted_manuscript = await manuscript_service.get_manuscript_by_id(test_manuscript.id, test_manuscript.user_id)
        assert deleted_manuscript is None
    
    async def test_delete_manuscript_not_found(self, async_client: AsyncClient, auth_headers: dict):
        """Test deletion of non-existent manuscript."""
        fake_id = str(ObjectId())
        
        response = await async_client.delete(
            f"/api/v1/manuscripts/{fake_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["success"] is False
    
    async def test_delete_manuscript_no_auth(self, async_client: AsyncClient, test_manuscript):
        """Test manuscript deletion without authentication."""
        response = await async_client.delete(f"/api/v1/manuscripts/{test_manuscript.id}")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

class TestManuscriptBulkOperations:
    """Test manuscript bulk operations."""
    
    async def test_bulk_delete_success(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test successful bulk deletion."""
        response = await async_client.post(
            "/api/v1/manuscripts/bulk-delete",
            json={"manuscript_ids": [str(test_manuscript.id)]},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["deleted_count"] == 1
        assert data["data"]["failed_count"] == 0
    
    async def test_bulk_delete_mixed_results(self, async_client: AsyncClient, auth_headers: dict, test_manuscript):
        """Test bulk deletion with mixed results."""
        fake_id = str(ObjectId())
        
        response = await async_client.post(
            "/api/v1/manuscripts/bulk-delete",
            json={"manuscript_ids": [str(test_manuscript.id), fake_id]},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["deleted_count"] == 1
        assert data["data"]["failed_count"] == 1
    
    async def test_bulk_delete_empty_list(self, async_client: AsyncClient, auth_headers: dict):
        """Test bulk deletion with empty list."""
        response = await async_client.post(
            "/api/v1/manuscripts/bulk-delete",
            json={"manuscript_ids": []},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
