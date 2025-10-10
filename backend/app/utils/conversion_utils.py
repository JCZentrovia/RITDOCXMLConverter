"""
Conversion utility functions for PDF processing and file management.
"""

import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
import mimetypes
import hashlib
import logging

logger = logging.getLogger(__name__)

class ConversionUtils:
    """Utility functions for file conversion operations."""

    @staticmethod
    def generate_conversion_id() -> str:
        """Generate a unique conversion ID."""
        return str(uuid.uuid4())

    @staticmethod
    def get_temp_directory() -> Path:
        """Get or create the temporary directory for conversions."""
        temp_dir = Path(tempfile.gettempdir()) / "manuscript_processor"
        temp_dir.mkdir(exist_ok=True)
        return temp_dir

    @staticmethod
    def generate_temp_filename(prefix: str = "conversion", suffix: str = "") -> str:
        """Generate a unique temporary filename."""
        unique_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{unique_id}{suffix}"

    @staticmethod
    def get_file_info(file_path: Path) -> Dict[str, Any]:
        """Get comprehensive file information."""
        try:
            stat = file_path.stat()
            
            # Get MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            # Calculate file hash
            file_hash = ConversionUtils.calculate_file_hash(file_path)
            
            return {
                "path": str(file_path),
                "name": file_path.name,
                "size_bytes": stat.st_size,
                "size_mb": stat.st_size / (1024 * 1024),
                "mime_type": mime_type,
                "extension": file_path.suffix.lower(),
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "hash_md5": file_hash,
                "exists": file_path.exists(),
                "is_file": file_path.is_file()
            }
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return {
                "path": str(file_path),
                "error": str(e),
                "exists": False
            }

    @staticmethod
    def calculate_file_hash(file_path: Path, algorithm: str = "md5") -> str:
        """Calculate file hash for integrity verification."""
        try:
            hash_obj = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate {algorithm} hash for {file_path}: {e}")
            return ""

    @staticmethod
    def validate_file_extension(file_path: Path, allowed_extensions: List[str]) -> bool:
        """Validate file extension against allowed list."""
        extension = file_path.suffix.lower()
        return extension in [ext.lower() for ext in allowed_extensions]

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage."""
        # Remove or replace unsafe characters
        unsafe_chars = '<>:"/\\|?*'
        sanitized = filename
        
        for char in unsafe_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Remove multiple consecutive underscores
        while '__' in sanitized:
            sanitized = sanitized.replace('__', '_')
        
        # Trim underscores from start and end
        sanitized = sanitized.strip('_')
        
        # Ensure filename is not empty
        if not sanitized:
            sanitized = "untitled"
        
        return sanitized

    @staticmethod
    def generate_s3_key(prefix: str, filename: str, user_id: Optional[str] = None) -> str:
        """Generate a safe S3 key for file storage."""
        sanitized_filename = ConversionUtils.sanitize_filename(filename)
        unique_id = str(uuid.uuid4())[:8]
        
        if user_id:
            return f"{prefix}/{user_id}/{unique_id}-{sanitized_filename}"
        else:
            return f"{prefix}/{unique_id}-{sanitized_filename}"

    @staticmethod
    def estimate_conversion_time(file_size_mb: float, page_count: int) -> float:
        """Estimate conversion time based on file characteristics."""
        # Base time per page (seconds)
        base_time_per_page = 2.0
        
        # Additional time based on file size
        size_factor = max(1.0, file_size_mb / 10.0)  # 1x for files up to 10MB
        
        # Calculate estimated time
        estimated_seconds = (page_count * base_time_per_page) * size_factor
        
        # Add buffer (20%)
        estimated_seconds *= 1.2
        
        return max(5.0, estimated_seconds)  # Minimum 5 seconds

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = int(seconds // 3600)
            remaining_minutes = int((seconds % 3600) // 60)
            return f"{hours}h {remaining_minutes}m"

    @staticmethod
    def cleanup_files(file_paths: List[Path], ignore_errors: bool = True) -> int:
        """Clean up multiple files and return count of successfully deleted files."""
        deleted_count = 0
        
        for file_path in file_paths:
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted file: {file_path}")
            except Exception as e:
                if not ignore_errors:
                    raise
                logger.warning(f"Failed to delete file {file_path}: {e}")
        
        return deleted_count

    @staticmethod
    def ensure_directory(directory_path: Path) -> None:
        """Ensure directory exists, create if it doesn't."""
        try:
            directory_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory {directory_path}: {e}")
            raise

    @staticmethod
    def get_conversion_quality_settings(quality: str) -> Dict[str, Any]:
        """Get conversion settings based on quality level."""
        quality_settings = {
            "standard": {
                "multi_processing": False,
                "cpu_count": 1,
                "image_resolution": 150,  # DPI
                "table_detection": True,
                "text_extraction": True,
                "preserve_formatting": True,
                "extract_images": True
            },
            "high": {
                "multi_processing": False,
                "cpu_count": 1,
                "image_resolution": 300,  # DPI
                "table_detection": True,
                "text_extraction": True,
                "preserve_formatting": True,
                "extract_images": True,
                "detailed_analysis": True
            }
        }
        
        return quality_settings.get(quality, quality_settings["standard"])

    @staticmethod
    def validate_conversion_limits(file_size_mb: float, page_count: int) -> Dict[str, Any]:
        """Validate file against conversion limits."""
        # Define limits
        MAX_FILE_SIZE_MB = 50
        MAX_PAGE_COUNT = 100
        
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check file size
        if file_size_mb > MAX_FILE_SIZE_MB:
            validation_result["valid"] = False
            validation_result["errors"].append(
                f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({MAX_FILE_SIZE_MB} MB)"
            )
        elif file_size_mb > MAX_FILE_SIZE_MB * 0.8:  # 80% of limit
            validation_result["warnings"].append(
                f"File size ({file_size_mb:.2f} MB) is close to the maximum limit ({MAX_FILE_SIZE_MB} MB)"
            )
        
        # Check page count
        if page_count > MAX_PAGE_COUNT:
            validation_result["valid"] = False
            validation_result["errors"].append(
                f"Page count ({page_count}) exceeds maximum allowed pages ({MAX_PAGE_COUNT})"
            )
        elif page_count > MAX_PAGE_COUNT * 0.8:  # 80% of limit
            validation_result["warnings"].append(
                f"Page count ({page_count}) is close to the maximum limit ({MAX_PAGE_COUNT})"
            )
        
        return validation_result

class ConversionMetrics:
    """Utility class for tracking conversion metrics."""
    
    @staticmethod
    def calculate_conversion_efficiency(
        input_size_mb: float,
        output_size_mb: float,
        conversion_time_seconds: float
    ) -> Dict[str, float]:
        """Calculate conversion efficiency metrics."""
        return {
            "compression_ratio": input_size_mb / output_size_mb if output_size_mb > 0 else 0,
            "processing_speed_mb_per_second": input_size_mb / conversion_time_seconds if conversion_time_seconds > 0 else 0,
            "size_reduction_percentage": ((input_size_mb - output_size_mb) / input_size_mb * 100) if input_size_mb > 0 else 0,
            "efficiency_score": (input_size_mb / conversion_time_seconds) if conversion_time_seconds > 0 else 0
        }

    @staticmethod
    def generate_conversion_report(
        conversion_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a comprehensive conversion report."""
        try:
            pdf_info = conversion_metadata.get("pdf_info", {})
            conversion_stats = conversion_metadata.get("conversion_stats", {})
            
            input_size_mb = pdf_info.get("size_mb", 0)
            output_size_mb = conversion_stats.get("output_size_mb", 0)
            conversion_time = conversion_metadata.get("conversion_duration_seconds", 0)
            
            efficiency_metrics = ConversionMetrics.calculate_conversion_efficiency(
                input_size_mb, output_size_mb, conversion_time
            )
            
            return {
                "conversion_id": conversion_metadata.get("conversion_id"),
                "success": conversion_metadata.get("success", False),
                "input_file": {
                    "size_mb": input_size_mb,
                    "pages": pdf_info.get("pages", 0),
                    "title": pdf_info.get("title", ""),
                    "author": pdf_info.get("author", "")
                },
                "output_file": {
                    "size_mb": output_size_mb,
                    "format": "docx"
                },
                "performance": {
                    "conversion_time_seconds": conversion_time,
                    "conversion_time_formatted": ConversionUtils.format_duration(conversion_time),
                    **efficiency_metrics
                },
                "quality": conversion_metadata.get("quality", "standard"),
                "timestamp": conversion_metadata.get("conversion_end")
            }
            
        except Exception as e:
            logger.error(f"Failed to generate conversion report: {e}")
            return {
                "error": str(e),
                "conversion_id": conversion_metadata.get("conversion_id"),
                "success": False
            }
