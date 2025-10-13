"""
Enhanced logging configuration for the manuscript processor application.

This module provides comprehensive logging setup with structured logging,
multiple handlers, log rotation, and performance monitoring.
"""

import logging
import logging.handlers
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from contextvars import ContextVar
import uuid

from app.core.config import settings

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
operation_var: ContextVar[Optional[str]] = ContextVar('operation', default=None)

class SimpleFormatter(logging.Formatter):
    """Simple human-readable formatter for console output."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as simple readable text."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname.ljust(5)
        
        # Get context information
        request_id = request_id_var.get()
        user_id = user_id_var.get()
        operation = operation_var.get()
        
        # Build context string
        context_parts = []
        if operation:
            context_parts.append(f"op:{operation}")
        if request_id:
            context_parts.append(f"req:{request_id}")
        if user_id:
            context_parts.append(f"user:{user_id[:8]}...")
        
        context_str = f"[{', '.join(context_parts)}]" if context_parts else ""
        
        # Format: TIME LEVEL [context] logger: message
        logger_name = record.name.split('.')[-1]  # Just the last part
        return f"{timestamp} {level} {context_str} {logger_name}: {record.getMessage()}"

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log structure
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add context information
        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id
            
        user_id = user_id_var.get()
        if user_id:
            log_entry["user_id"] = user_id
            
        operation = operation_var.get()
        if operation:
            log_entry["operation"] = operation
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'getMessage'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)

class PerformanceFormatter(logging.Formatter):
    """Formatter for performance and timing logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format performance log record."""
        
        performance_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "performance",
            "operation": getattr(record, 'operation', 'unknown'),
            "duration_ms": getattr(record, 'duration_ms', 0),
            "status": getattr(record, 'status', 'unknown'),
            "details": getattr(record, 'details', {})
        }
        
        # Add context
        request_id = request_id_var.get()
        if request_id:
            performance_entry["request_id"] = request_id
            
        user_id = user_id_var.get()
        if user_id:
            performance_entry["user_id"] = user_id
        
        return json.dumps(performance_entry, default=str, ensure_ascii=False)

class ConversionFormatter(logging.Formatter):
    """Specialized formatter for conversion process logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format conversion log record."""
        
        conversion_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "conversion",
            "level": record.levelname,
            "message": record.getMessage(),
            "conversion_id": getattr(record, 'conversion_id', None),
            "manuscript_id": getattr(record, 'manuscript_id', None),
            "user_id": getattr(record, 'user_id', None),
            "status": getattr(record, 'status', None),
            "progress": getattr(record, 'progress', None),
            "error_code": getattr(record, 'error_code', None),
            "retry_count": getattr(record, 'retry_count', None),
        }
        
        # Add conversion metadata if present
        metadata = getattr(record, 'metadata', None)
        if metadata:
            conversion_entry["metadata"] = metadata
        
        # Add exception information
        if record.exc_info:
            conversion_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(conversion_entry, default=str, ensure_ascii=False)

def setup_logging() -> None:
    """Setup comprehensive logging configuration."""
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler with simple human-readable logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(SimpleFormatter())
    root_logger.addHandler(console_handler)
    
    # Application log file handler
    app_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "application.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    app_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    app_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(app_handler)
    
    # Error log file handler
    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(error_handler)
    
    # Performance log handler
    performance_logger = logging.getLogger("performance")
    performance_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "performance.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    performance_handler.setLevel(logging.INFO)
    performance_handler.setFormatter(PerformanceFormatter())
    performance_logger.addHandler(performance_handler)
    performance_logger.propagate = False
    
    # Conversion log handler
    conversion_logger = logging.getLogger("conversion")
    conversion_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "conversions.log",
        maxBytes=20 * 1024 * 1024,  # 20MB
        backupCount=5,
        encoding='utf-8'
    )
    conversion_handler.setLevel(logging.INFO)
    conversion_handler.setFormatter(ConversionFormatter())
    conversion_logger.addHandler(conversion_handler)
    conversion_logger.propagate = False
    
    # Security log handler
    security_logger = logging.getLogger("security")
    security_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "security.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=10,
        encoding='utf-8'
    )
    security_handler.setLevel(logging.WARNING)
    security_handler.setFormatter(StructuredFormatter())
    security_logger.addHandler(security_handler)
    security_logger.propagate = False
    
    # Database log handler
    db_logger = logging.getLogger("database")
    db_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "database.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    db_handler.setLevel(logging.INFO)
    db_handler.setFormatter(StructuredFormatter())
    db_logger.addHandler(db_handler)
    db_logger.propagate = False
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logging.info("Logging system initialized", extra={
        "logs_directory": str(logs_dir),
        "debug_mode": settings.debug,
        "handlers_count": len(root_logger.handlers)
    })

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)

def set_request_context(request_id: str = None, user_id: str = None, operation: str = None) -> None:
    """Set request context for logging."""
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if operation:
        operation_var.set(operation)

def clear_request_context() -> None:
    """Clear request context."""
    request_id_var.set(None)
    user_id_var.set(None)
    operation_var.set(None)

def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())[:8]

class LoggingContext:
    """Context manager for logging with automatic context management."""
    
    def __init__(self, operation: str, user_id: str = None, **kwargs):
        self.operation = operation
        self.user_id = user_id
        self.request_id = generate_request_id()
        self.kwargs = kwargs
        self.start_time = None
        self.logger = get_logger(f"context.{operation}")
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        set_request_context(
            request_id=self.request_id,
            user_id=self.user_id,
            operation=self.operation
        )
        
        self.logger.info(f"Started {self.operation}", extra={
            "operation_start": True,
            **self.kwargs
        })
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.utcnow()
        duration_ms = (end_time - self.start_time).total_seconds() * 1000
        
        if exc_type:
            self.logger.error(f"Failed {self.operation}", extra={
                "operation_end": True,
                "success": False,
                "duration_ms": duration_ms,
                "error_type": exc_type.__name__,
                "error_message": str(exc_val),
                **self.kwargs
            }, exc_info=(exc_type, exc_val, exc_tb))
        else:
            self.logger.info(f"Completed {self.operation}", extra={
                "operation_end": True,
                "success": True,
                "duration_ms": duration_ms,
                **self.kwargs
            })
        
        clear_request_context()

class PerformanceLogger:
    """Logger for performance monitoring."""
    
    def __init__(self):
        self.logger = get_logger("performance")
    
    def log_operation(self, operation: str, duration_ms: float, status: str = "success", **details):
        """Log a performance operation."""
        self.logger.info("Performance metric", extra={
            "operation": operation,
            "duration_ms": duration_ms,
            "status": status,
            "details": details
        })
    
    def log_conversion_performance(self, conversion_id: str, manuscript_id: str, 
                                 duration_ms: float, input_size_mb: float, 
                                 output_size_mb: float, status: str = "success"):
        """Log conversion performance metrics."""
        self.logger.info("Conversion performance", extra={
            "operation": "pdf_conversion",
            "duration_ms": duration_ms,
            "status": status,
            "details": {
                "conversion_id": conversion_id,
                "manuscript_id": manuscript_id,
                "input_size_mb": input_size_mb,
                "output_size_mb": output_size_mb,
                "processing_speed_mb_per_sec": input_size_mb / (duration_ms / 1000) if duration_ms > 0 else 0,
                "compression_ratio": input_size_mb / output_size_mb if output_size_mb > 0 else 0
            }
        })

class ConversionLogger:
    """Specialized logger for conversion processes."""
    
    def __init__(self):
        self.logger = get_logger("conversion")
    
    def log_conversion_start(self, conversion_id: str, manuscript_id: str, user_id: str, 
                           quality: str, priority: int):
        """Log conversion start."""
        self.logger.info("Conversion started", extra={
            "conversion_id": conversion_id,
            "manuscript_id": manuscript_id,
            "user_id": user_id,
            "status": "started",
            "metadata": {
                "quality": quality,
                "priority": priority
            }
        })
    
    def log_conversion_progress(self, conversion_id: str, manuscript_id: str, 
                              progress: int, status: str, message: str = ""):
        """Log conversion progress."""
        self.logger.info(f"Conversion progress: {message}", extra={
            "conversion_id": conversion_id,
            "manuscript_id": manuscript_id,
            "status": status,
            "progress": progress
        })
    
    def log_conversion_success(self, conversion_id: str, manuscript_id: str, 
                             xml_s3_key: str = None, docx_s3_key: str = None, metadata: Dict[str, Any] = None):
        """Log successful conversion."""
        if metadata is None:
            metadata = {}
        
        result_metadata = {**metadata}
        if xml_s3_key:
            result_metadata["xml_s3_key"] = xml_s3_key
        if docx_s3_key:
            result_metadata["docx_s3_key"] = docx_s3_key
            
        self.logger.info("Conversion completed successfully", extra={
            "conversion_id": conversion_id,
            "manuscript_id": manuscript_id,
            "status": "completed",
            "progress": 100,
            "metadata": result_metadata
        })
    
    def log_conversion_error(self, conversion_id: str, manuscript_id: str, 
                           error_code: str, error_message: str, retry_count: int = 0):
        """Log conversion error."""
        self.logger.error("Conversion failed", extra={
            "conversion_id": conversion_id,
            "manuscript_id": manuscript_id,
            "status": "failed",
            "error_code": error_code,
            "retry_count": retry_count,
            "metadata": {
                "error_message": error_message
            }
        })
    
    def log_conversion_retry(self, conversion_id: str, manuscript_id: str, 
                           retry_count: int, max_retries: int, reason: str):
        """Log conversion retry."""
        self.logger.warning("Conversion retry", extra={
            "conversion_id": conversion_id,
            "manuscript_id": manuscript_id,
            "status": "retrying",
            "retry_count": retry_count,
            "metadata": {
                "max_retries": max_retries,
                "reason": reason
            }
        })

class SecurityLogger:
    """Logger for security events."""
    
    def __init__(self):
        self.logger = get_logger("security")
    
    def log_authentication_failure(self, email: str, ip_address: str, reason: str):
        """Log authentication failure."""
        self.logger.warning("Authentication failed", extra={
            "event_type": "auth_failure",
            "email": email,
            "ip_address": ip_address,
            "reason": reason
        })
    
    def log_unauthorized_access(self, user_id: str, resource: str, action: str, ip_address: str):
        """Log unauthorized access attempt."""
        self.logger.warning("Unauthorized access attempt", extra={
            "event_type": "unauthorized_access",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "ip_address": ip_address
        })
    
    def log_suspicious_activity(self, user_id: str, activity: str, details: Dict[str, Any]):
        """Log suspicious activity."""
        self.logger.warning("Suspicious activity detected", extra={
            "event_type": "suspicious_activity",
            "user_id": user_id,
            "activity": activity,
            "details": details
        })

# Global logger instances
performance_logger = PerformanceLogger()
conversion_logger = ConversionLogger()
security_logger = SecurityLogger()
