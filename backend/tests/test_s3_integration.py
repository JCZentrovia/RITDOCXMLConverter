"""
Integration tests for S3 service operations.

This module tests S3 connectivity, file upload/download operations,
presigned URL generation, and error handling.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import tempfile
import io

from app.services.s3_service import s3_service, S3Service
from app.core.config import settings

pytestmark = [pytest.mark.asyncio, pytest.mark.integration, pytest.mark.s3]

class TestS3ServiceInitialization:
    """Test S3 service initialization and configuration."""
    
    def test_s3_service_initialization(self):
        """Test S3 service is properly initialized."""
        assert s3_service is not None
        assert s3_service.bucket_name == settings.s3_bucket_name
        assert s3_service.region == settings.aws_region
    
    def test_s3_client_configuration(self):
        """Test S3 client configuration."""
        # Test that client is configured
        assert s3_service.client is not None
        
        # Test region configuration
        client_region = s3_service.client.meta.region_name
        assert client_region == settings.aws_region

class TestS3BucketOperations:
    """Test S3 bucket-level operations."""
    
    @patch('app.services.s3_service.s3_service.client')
    def test_check_bucket_access_success(self, mock_client):
        """Test successful bucket access check."""
        # Mock successful head_bucket operation
        mock_client.head_bucket.return_value = {}
        
        result = s3_service.check_bucket_access()
        
        assert result is True
        mock_client.head_bucket.assert_called_once_with(Bucket=settings.s3_bucket_name)
    
    @patch('app.services.s3_service.s3_service.client')
    def test_check_bucket_access_failure(self, mock_client):
        """Test bucket access check failure."""
        # Mock failed head_bucket operation
        from botocore.exceptions import ClientError
        mock_client.head_bucket.side_effect = ClientError(
            error_response={'Error': {'Code': '403', 'Message': 'Forbidden'}},
            operation_name='HeadBucket'
        )
        
        result = s3_service.check_bucket_access()
        
        assert result is False
        mock_client.head_bucket.assert_called_once_with(Bucket=settings.s3_bucket_name)
    
    @patch('app.services.s3_service.s3_service.client')
    def test_list_bucket_objects(self, mock_client):
        """Test listing bucket objects."""
        # Mock list_objects_v2 response
        mock_response = {
            'Contents': [
                {
                    'Key': 'test-pdfs/document1.pdf',
                    'LastModified': datetime.utcnow(),
                    'Size': 1024000
                },
                {
                    'Key': 'test-pdfs/document2.pdf',
                    'LastModified': datetime.utcnow(),
                    'Size': 2048000
                }
            ]
        }
        mock_client.list_objects_v2.return_value = mock_response
        
        objects = s3_service.list_objects(prefix="test-pdfs/")
        
        assert len(objects) == 2
        assert objects[0]['Key'] == 'test-pdfs/document1.pdf'
        assert objects[1]['Key'] == 'test-pdfs/document2.pdf'
        
        mock_client.list_objects_v2.assert_called_once_with(
            Bucket=settings.s3_bucket_name,
            Prefix="test-pdfs/"
        )

class TestPresignedURLGeneration:
    """Test presigned URL generation for uploads and downloads."""
    
    @patch('app.services.s3_service.s3_service.client')
    def test_generate_presigned_upload_url_success(self, mock_client):
        """Test successful presigned upload URL generation."""
        # Mock generate_presigned_post response
        mock_response = {
            'url': 'https://test-bucket.s3.amazonaws.com/',
            'fields': {
                'key': 'test-pdfs/test-document.pdf',
                'AWSAccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'policy': 'eyJleHBpcmF0aW9uIjoiMjAyMy0xMi0zMVQyMzo1OTo1OVoiLCJjb25kaXRpb25zIjpbXX0=',
                'signature': 'signature-string'
            }
        }
        mock_client.generate_presigned_post.return_value = mock_response
        
        result = s3_service.generate_presigned_upload_url(
            filename="test-document.pdf",
            content_type="application/pdf",
            file_size=1024000
        )
        
        assert result is not None
        assert 'upload_url' in result
        assert 'fields' in result
        assert 's3_key' in result
        assert result['upload_url'] == mock_response['url']
        assert result['fields'] == mock_response['fields']
        
        mock_client.generate_presigned_post.assert_called_once()
    
    @patch('app.services.s3_service.s3_service.client')
    def test_generate_presigned_download_url_success(self, mock_client):
        """Test successful presigned download URL generation."""
        # Mock generate_presigned_url response
        mock_url = 'https://test-bucket.s3.amazonaws.com/test-pdfs/test-document.pdf?signature=test'
        mock_client.generate_presigned_url.return_value = mock_url
        
        s3_key = "test-pdfs/test-document.pdf"
        result = s3_service.generate_presigned_download_url(s3_key)
        
        assert result == mock_url
        
        mock_client.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': settings.s3_bucket_name, 'Key': s3_key},
            ExpiresIn=3600  # Default expiration
        )
    
    @patch('app.services.s3_service.s3_service.client')
    def test_generate_presigned_download_url_with_custom_expiration(self, mock_client):
        """Test presigned download URL with custom expiration."""
        mock_url = 'https://test-bucket.s3.amazonaws.com/test-pdfs/test-document.pdf?signature=test'
        mock_client.generate_presigned_url.return_value = mock_url
        
        s3_key = "test-pdfs/test-document.pdf"
        custom_expiration = 7200  # 2 hours
        
        result = s3_service.generate_presigned_download_url(s3_key, expires_in=custom_expiration)
        
        assert result == mock_url
        
        mock_client.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': settings.s3_bucket_name, 'Key': s3_key},
            ExpiresIn=custom_expiration
        )
    
    @patch('app.services.s3_service.s3_service.client')
    def test_generate_presigned_url_error_handling(self, mock_client):
        """Test presigned URL generation error handling."""
        from botocore.exceptions import ClientError
        
        # Mock client error
        mock_client.generate_presigned_url.side_effect = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}},
            operation_name='GetObject'
        )
        
        s3_key = "nonexistent/file.pdf"
        
        with pytest.raises(Exception):  # Should raise some form of exception
            s3_service.generate_presigned_download_url(s3_key)

class TestFileOperations:
    """Test file upload, download, and manipulation operations."""
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_upload_file_success(self, mock_client):
        """Test successful file upload."""
        # Mock put_object response
        mock_response = {
            'ETag': '"d41d8cd98f00b204e9800998ecf8427e"',
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_client.put_object.return_value = mock_response
        
        # Create test file content
        file_content = b"Test PDF content"
        file_obj = io.BytesIO(file_content)
        s3_key = "test-pdfs/uploaded-document.pdf"
        
        result = await s3_service.upload_file(file_obj, s3_key, "application/pdf")
        
        assert result is True
        
        mock_client.put_object.assert_called_once_with(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=file_obj,
            ContentType="application/pdf"
        )
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_upload_file_failure(self, mock_client):
        """Test file upload failure."""
        from botocore.exceptions import ClientError
        
        # Mock client error
        mock_client.put_object.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            operation_name='PutObject'
        )
        
        file_content = b"Test PDF content"
        file_obj = io.BytesIO(file_content)
        s3_key = "test-pdfs/upload-fail.pdf"
        
        result = await s3_service.upload_file(file_obj, s3_key, "application/pdf")
        
        assert result is False
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_download_file_success(self, mock_client):
        """Test successful file download."""
        # Mock get_object response
        file_content = b"Test PDF content"
        mock_response = {
            'Body': io.BytesIO(file_content),
            'ContentType': 'application/pdf',
            'ContentLength': len(file_content)
        }
        mock_client.get_object.return_value = mock_response
        
        s3_key = "test-pdfs/download-test.pdf"
        result = await s3_service.download_file(s3_key)
        
        assert result is not None
        assert result == file_content
        
        mock_client.get_object.assert_called_once_with(
            Bucket=settings.s3_bucket_name,
            Key=s3_key
        )
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_download_file_not_found(self, mock_client):
        """Test file download when file doesn't exist."""
        from botocore.exceptions import ClientError
        
        # Mock NoSuchKey error
        mock_client.get_object.side_effect = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}},
            operation_name='GetObject'
        )
        
        s3_key = "nonexistent/file.pdf"
        result = await s3_service.download_file(s3_key)
        
        assert result is None
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_delete_file_success(self, mock_client):
        """Test successful file deletion."""
        # Mock delete_object response
        mock_response = {
            'ResponseMetadata': {'HTTPStatusCode': 204}
        }
        mock_client.delete_object.return_value = mock_response
        
        s3_key = "test-pdfs/delete-test.pdf"
        result = await s3_service.delete_file(s3_key)
        
        assert result is True
        
        mock_client.delete_object.assert_called_once_with(
            Bucket=settings.s3_bucket_name,
            Key=s3_key
        )
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_delete_file_failure(self, mock_client):
        """Test file deletion failure."""
        from botocore.exceptions import ClientError
        
        # Mock client error
        mock_client.delete_object.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            operation_name='DeleteObject'
        )
        
        s3_key = "test-pdfs/delete-fail.pdf"
        result = await s3_service.delete_file(s3_key)
        
        assert result is False

class TestFileMetadata:
    """Test file metadata operations."""
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_get_file_metadata_success(self, mock_client):
        """Test successful file metadata retrieval."""
        # Mock head_object response
        mock_response = {
            'ContentLength': 1024000,
            'ContentType': 'application/pdf',
            'LastModified': datetime.utcnow(),
            'ETag': '"d41d8cd98f00b204e9800998ecf8427e"',
            'Metadata': {
                'original-name': 'Test Document.pdf',
                'uploaded-by': 'test-user'
            }
        }
        mock_client.head_object.return_value = mock_response
        
        s3_key = "test-pdfs/metadata-test.pdf"
        metadata = await s3_service.get_file_metadata(s3_key)
        
        assert metadata is not None
        assert metadata['size'] == 1024000
        assert metadata['content_type'] == 'application/pdf'
        assert 'last_modified' in metadata
        assert metadata['etag'] == '"d41d8cd98f00b204e9800998ecf8427e"'
        
        mock_client.head_object.assert_called_once_with(
            Bucket=settings.s3_bucket_name,
            Key=s3_key
        )
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_get_file_metadata_not_found(self, mock_client):
        """Test file metadata retrieval when file doesn't exist."""
        from botocore.exceptions import ClientError
        
        # Mock NoSuchKey error
        mock_client.head_object.side_effect = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}},
            operation_name='HeadObject'
        )
        
        s3_key = "nonexistent/file.pdf"
        metadata = await s3_service.get_file_metadata(s3_key)
        
        assert metadata is None
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_file_exists_true(self, mock_client):
        """Test file existence check when file exists."""
        # Mock successful head_object
        mock_response = {
            'ContentLength': 1024000,
            'ContentType': 'application/pdf'
        }
        mock_client.head_object.return_value = mock_response
        
        s3_key = "test-pdfs/existing-file.pdf"
        exists = await s3_service.file_exists(s3_key)
        
        assert exists is True
        
        mock_client.head_object.assert_called_once_with(
            Bucket=settings.s3_bucket_name,
            Key=s3_key
        )
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_file_exists_false(self, mock_client):
        """Test file existence check when file doesn't exist."""
        from botocore.exceptions import ClientError
        
        # Mock NoSuchKey error
        mock_client.head_object.side_effect = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}},
            operation_name='HeadObject'
        )
        
        s3_key = "nonexistent/file.pdf"
        exists = await s3_service.file_exists(s3_key)
        
        assert exists is False

class TestS3KeyGeneration:
    """Test S3 key generation and validation."""
    
    def test_generate_s3_key_pdf(self):
        """Test S3 key generation for PDF files."""
        filename = "test_document.pdf"
        user_id = "user123"
        
        s3_key = s3_service.generate_s3_key(filename, user_id, file_type="pdf")
        
        assert s3_key.startswith("pdfs/")
        assert user_id in s3_key
        assert filename in s3_key
        assert s3_key.endswith(".pdf")
    
    def test_generate_s3_key_docx(self):
        """Test S3 key generation for DOCX files."""
        filename = "converted_document.docx"
        user_id = "user123"
        
        s3_key = s3_service.generate_s3_key(filename, user_id, file_type="docx")
        
        assert s3_key.startswith("docx/")
        assert user_id in s3_key
        assert filename in s3_key
        assert s3_key.endswith(".docx")
    
    def test_generate_s3_key_with_special_characters(self):
        """Test S3 key generation with special characters in filename."""
        filename = "test document with spaces & symbols!.pdf"
        user_id = "user123"
        
        s3_key = s3_service.generate_s3_key(filename, user_id, file_type="pdf")
        
        # Should sanitize special characters
        assert " " not in s3_key or "_" in s3_key  # Spaces should be replaced
        assert "&" not in s3_key
        assert "!" not in s3_key
    
    def test_validate_s3_key_valid(self):
        """Test S3 key validation with valid keys."""
        valid_keys = [
            "pdfs/user123/document.pdf",
            "docx/user456/converted.docx",
            "pdfs/user789/test_file_name.pdf"
        ]
        
        for key in valid_keys:
            assert s3_service.validate_s3_key(key) is True
    
    def test_validate_s3_key_invalid(self):
        """Test S3 key validation with invalid keys."""
        invalid_keys = [
            "",  # Empty key
            "invalid-prefix/file.pdf",  # Invalid prefix
            "pdfs/",  # Missing filename
            "pdfs/user/file.txt",  # Invalid extension
            "../pdfs/user/file.pdf",  # Path traversal attempt
        ]
        
        for key in invalid_keys:
            assert s3_service.validate_s3_key(key) is False

class TestS3ErrorHandling:
    """Test S3 service error handling."""
    
    @patch('app.services.s3_service.s3_service.client')
    def test_handle_client_error_access_denied(self, mock_client):
        """Test handling of access denied errors."""
        from botocore.exceptions import ClientError
        
        # Mock access denied error
        mock_client.head_bucket.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
            operation_name='HeadBucket'
        )
        
        result = s3_service.check_bucket_access()
        
        assert result is False
    
    @patch('app.services.s3_service.s3_service.client')
    def test_handle_client_error_no_such_bucket(self, mock_client):
        """Test handling of no such bucket errors."""
        from botocore.exceptions import ClientError
        
        # Mock no such bucket error
        mock_client.head_bucket.side_effect = ClientError(
            error_response={'Error': {'Code': 'NoSuchBucket', 'Message': 'The specified bucket does not exist'}},
            operation_name='HeadBucket'
        )
        
        result = s3_service.check_bucket_access()
        
        assert result is False
    
    @patch('app.services.s3_service.s3_service.client')
    async def test_handle_network_error(self, mock_client):
        """Test handling of network errors."""
        from botocore.exceptions import EndpointConnectionError
        
        # Mock network error
        mock_client.head_object.side_effect = EndpointConnectionError(
            endpoint_url="https://s3.amazonaws.com"
        )
        
        s3_key = "test-pdfs/network-error.pdf"
        
        # Should handle gracefully and return None/False
        metadata = await s3_service.get_file_metadata(s3_key)
        assert metadata is None

class TestS3ServiceConfiguration:
    """Test S3 service configuration and setup."""
    
    def test_s3_service_with_custom_config(self):
        """Test S3 service with custom configuration."""
        custom_service = S3Service(
            bucket_name="custom-bucket",
            region="us-west-2"
        )
        
        assert custom_service.bucket_name == "custom-bucket"
        assert custom_service.region == "us-west-2"
    
    def test_s3_service_with_profile(self):
        """Test S3 service with AWS profile."""
        # Test that service can be initialized with profile
        try:
            profile_service = S3Service(
                bucket_name=settings.s3_bucket_name,
                region=settings.aws_region,
                profile_name="jadmin"  # Test profile
            )
            assert profile_service is not None
        except Exception:
            # Profile might not exist in test environment
            pytest.skip("AWS profile 'jadmin' not available in test environment")
    
    def test_s3_service_environment_variables(self):
        """Test S3 service respects environment variables."""
        # Test that service uses environment configuration
        assert s3_service.bucket_name == settings.s3_bucket_name
        assert s3_service.region == settings.aws_region

class TestS3IntegrationWithFiles:
    """Test S3 integration with actual file operations."""
    
    async def test_upload_download_cycle(self, sample_pdf_file: Path):
        """Test complete upload-download cycle with mock S3."""
        with patch('app.services.s3_service.s3_service.client') as mock_client:
            # Read sample file
            file_content = sample_pdf_file.read_bytes()
            
            # Mock upload
            mock_client.put_object.return_value = {
                'ETag': '"test-etag"',
                'ResponseMetadata': {'HTTPStatusCode': 200}
            }
            
            # Mock download
            mock_client.get_object.return_value = {
                'Body': io.BytesIO(file_content),
                'ContentType': 'application/pdf',
                'ContentLength': len(file_content)
            }
            
            # Test upload
            file_obj = io.BytesIO(file_content)
            s3_key = "test-pdfs/integration-test.pdf"
            
            upload_result = await s3_service.upload_file(file_obj, s3_key, "application/pdf")
            assert upload_result is True
            
            # Test download
            downloaded_content = await s3_service.download_file(s3_key)
            assert downloaded_content == file_content
    
    async def test_file_metadata_consistency(self, sample_pdf_file: Path):
        """Test file metadata consistency."""
        with patch('app.services.s3_service.s3_service.client') as mock_client:
            file_content = sample_pdf_file.read_bytes()
            file_size = len(file_content)
            
            # Mock metadata response
            mock_client.head_object.return_value = {
                'ContentLength': file_size,
                'ContentType': 'application/pdf',
                'LastModified': datetime.utcnow(),
                'ETag': '"test-etag"'
            }
            
            s3_key = "test-pdfs/metadata-consistency.pdf"
            metadata = await s3_service.get_file_metadata(s3_key)
            
            assert metadata is not None
            assert metadata['size'] == file_size
            assert metadata['content_type'] == 'application/pdf'
