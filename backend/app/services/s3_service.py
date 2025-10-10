"""
AWS S3 service for file operations using role-based access.
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """AWS S3 service using role-based access (IAM roles)."""
    
    def __init__(self):
        """Initialize S3 client with jadmin profile or environment variables."""
        try:
            # Try to use jadmin profile first (for local development)
            try:
                session = boto3.Session(profile_name='jadmin')
                self.s3_client = session.client(
                    's3',
                    region_name=settings.aws_region
                )
                logger.info(f"S3 client initialized with jadmin profile for region: {settings.aws_region}")
            except Exception as profile_error:
                # Fallback to environment variables or IAM role (for Docker/ECS)
                logger.info(f"jadmin profile not found ({profile_error}), using environment variables or IAM role")
                self.s3_client = boto3.client(
                    's3',
                    region_name=settings.aws_region
                )
                logger.info(f"S3 client initialized with environment variables/IAM role for region: {settings.aws_region}")
                
        except NoCredentialsError:
            logger.error("AWS credentials not found. Ensure jadmin profile is configured or AWS environment variables are set.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def generate_presigned_upload_url(
        self, 
        key: str, 
        content_type: str = "application/pdf",
        expires_in: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for uploading files to S3.
        
        Args:
            key: S3 object key (file path)
            content_type: MIME type of the file
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned upload URL or None if failed
        """
        try:
            # Include Content-Type in presigned URL to match frontend request
            response = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.s3_bucket_name,
                    'Key': key,
                    'ContentType': content_type
                },
                ExpiresIn=expires_in
            )
            logger.info(f"Generated presigned upload URL for key: {key} with content-type: {content_type}")
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned upload URL: {e}")
            return None
    
    def generate_presigned_download_url(
        self, 
        key: str, 
        expires_in: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for downloading files from S3.
        
        Args:
            key: S3 object key (file path)
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned download URL or None if failed
        """
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.s3_bucket_name,
                    'Key': key
                },
                ExpiresIn=expires_in
            )
            logger.info(f"Generated presigned download URL for key: {key}")
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned download URL: {e}")
            return None
    
    def download_file(self, key: str, local_path: str) -> bool:
        """
        Download a file from S3 to local storage.
        
        Args:
            key: S3 object key (file path)
            local_path: Local file path to save the downloaded file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.download_file(
                settings.s3_bucket_name,
                key,
                local_path
            )
            logger.info(f"Downloaded file from S3: {key} -> {local_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            return False
    
    def upload_file(self, local_path: str, key: str, content_type: str = None) -> bool:
        """
        Upload a file from local storage to S3.
        
        Args:
            local_path: Local file path
            key: S3 object key (file path)
            content_type: MIME type of the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
                
            self.s3_client.upload_file(
                local_path,
                settings.s3_bucket_name,
                key,
                ExtraArgs=extra_args
            )
            logger.info(f"Uploaded file to S3: {local_path} -> {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            return False
    
    def delete_file(self, key: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            key: S3 object key (file path)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=settings.s3_bucket_name,
                Key=key
            )
            logger.info(f"Deleted file from S3: {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
    
    def check_bucket_access(self) -> bool:
        """
        Check if the S3 bucket is accessible with current IAM role.
        
        Returns:
            True if accessible, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=settings.s3_bucket_name)
            logger.info(f"S3 bucket access confirmed: {settings.s3_bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"S3 bucket access failed: {e}")
            return False


# Global S3 service instance
s3_service = S3Service()
