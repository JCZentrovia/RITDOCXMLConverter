"""
Application configuration settings.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # MongoDB Atlas Configuration
    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_database: str = "manuscript_processor"
    mongodb_username: Optional[str] = None
    mongodb_password: Optional[str] = None
    
    # JWT Configuration
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # AWS S3 Configuration (Role-based access)
    aws_region: str = "us-east-1"
    s3_bucket_name: str = "manuscript-processor-bucket"
    
    # OpenAI Configuration
    openai_api_key: str = ""
    
    # Application Configuration
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    # Maximum allowed upload size (in MB) for presigned uploads
    max_upload_size_mb: int = 100
    
    # Scheduler Configuration
    scheduler_interval_seconds: int = 10
    
    @property
    def mongodb_url(self) -> str:
        """Construct MongoDB Atlas connection string."""
        if self.mongodb_username and self.mongodb_password:
            # MongoDB Atlas connection string
            return f"mongodb+srv://{self.mongodb_username}:{self.mongodb_password}@{self.mongodb_host}/{self.mongodb_database}?retryWrites=true&w=majority"
        else:
            # Local MongoDB connection string
            return f"mongodb://{self.mongodb_host}:{self.mongodb_port}"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
