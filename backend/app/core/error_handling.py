"""
Enhanced error handling system for the manuscript processor application.

This module provides comprehensive error handling, classification, recovery strategies,
and detailed error reporting for all application components.
"""

import logging
import traceback
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Type
from dataclasses import dataclass, field
import uuid

from fastapi import HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ErrorCategory(str, Enum):
    """Error categories for classification and handling."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    CONVERSION = "conversion"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORK = "network"
    SYSTEM = "system"
    BUSINESS_LOGIC = "business_logic"
    RATE_LIMIT = "rate_limit"
    MAINTENANCE = "maintenance"

class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RecoveryStrategy(str, Enum):
    """Recovery strategies for different error types."""
    RETRY = "retry"
    FALLBACK = "fallback"
    ROLLBACK = "rollback"
    MANUAL_INTERVENTION = "manual_intervention"
    IGNORE = "ignore"
    ESCALATE = "escalate"

@dataclass
class ErrorContext:
    """Context information for error handling."""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    operation: Optional[str] = None
    resource_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    additional_data: Dict[str, Any] = field(default_factory=dict)

class ApplicationError(Exception):
    """Base application error with enhanced context and handling."""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.MANUAL_INTERVENTION,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        user_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.recovery_strategy = recovery_strategy
        self.context = context or ErrorContext()
        self.cause = cause
        self.user_message = user_message or self._generate_user_message()
        self.details = details or {}
        self.error_id = str(uuid.uuid4())[:8]
        
        # Log the error
        self._log_error()
    
    def _generate_user_message(self) -> str:
        """Generate a user-friendly error message."""
        user_messages = {
            ErrorCategory.VALIDATION: "The provided information is invalid. Please check your input and try again.",
            ErrorCategory.AUTHENTICATION: "Authentication failed. Please check your credentials and try again.",
            ErrorCategory.AUTHORIZATION: "You don't have permission to perform this action.",
            ErrorCategory.NOT_FOUND: "The requested resource was not found.",
            ErrorCategory.CONFLICT: "The operation conflicts with the current state. Please refresh and try again.",
            ErrorCategory.CONVERSION: "File conversion failed. Please try again or contact support if the problem persists.",
            ErrorCategory.STORAGE: "File storage operation failed. Please try again later.",
            ErrorCategory.DATABASE: "A database error occurred. Please try again later.",
            ErrorCategory.NETWORK: "A network error occurred. Please check your connection and try again.",
            ErrorCategory.SYSTEM: "A system error occurred. Please try again later or contact support.",
            ErrorCategory.BUSINESS_LOGIC: "The operation cannot be completed due to business rules.",
            ErrorCategory.RATE_LIMIT: "Too many requests. Please wait before trying again.",
            ErrorCategory.MAINTENANCE: "The system is currently under maintenance. Please try again later."
        }
        return user_messages.get(self.category, "An unexpected error occurred. Please try again later.")
    
    def _log_error(self) -> None:
        """Log the error with appropriate level and context."""
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }.get(self.severity, logging.ERROR)
        
        logger.log(log_level, f"Application error: {self.message}", extra={
            "error_id": self.error_id,
            "error_code": self.error_code,
            "category": self.category.value,
            "severity": self.severity.value,
            "recovery_strategy": self.recovery_strategy.value,
            "context": {
                "request_id": self.context.request_id,
                "user_id": self.context.user_id,
                "operation": self.context.operation,
                "resource_id": self.context.resource_id,
                "additional_data": self.context.additional_data
            },
            "details": self.details,
            "cause": str(self.cause) if self.cause else None
        }, exc_info=self.cause if self.cause else None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "recovery_strategy": self.recovery_strategy.value,
            "timestamp": self.context.timestamp.isoformat(),
            "details": self.details,
            "context": {
                "request_id": self.context.request_id,
                "user_id": self.context.user_id,
                "operation": self.context.operation,
                "resource_id": self.context.resource_id
            }
        }

class ValidationError(ApplicationError):
    """Validation error."""
    
    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        details = kwargs.pop('details', {})
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            recovery_strategy=RecoveryStrategy.RETRY,
            details=details,
            **kwargs
        )

class ConversionError(ApplicationError):
    """PDF conversion error."""
    
    def __init__(self, message: str, conversion_id: str = None, manuscript_id: str = None, **kwargs):
        details = kwargs.pop('details', {})
        if conversion_id:
            details['conversion_id'] = conversion_id
        if manuscript_id:
            details['manuscript_id'] = manuscript_id
        
        super().__init__(
            message=message,
            error_code="CONVERSION_ERROR",
            category=ErrorCategory.CONVERSION,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.RETRY,
            details=details,
            **kwargs
        )

class StorageError(ApplicationError):
    """S3 storage error."""
    
    def __init__(self, message: str, s3_key: str = None, operation: str = None, **kwargs):
        details = kwargs.pop('details', {})
        if s3_key:
            details['s3_key'] = s3_key
        if operation:
            details['operation'] = operation
        
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            category=ErrorCategory.STORAGE,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.RETRY,
            details=details,
            **kwargs
        )

class DatabaseError(ApplicationError):
    """Database operation error."""
    
    def __init__(self, message: str, collection: str = None, operation: str = None, **kwargs):
        details = kwargs.pop('details', {})
        if collection:
            details['collection'] = collection
        if operation:
            details['operation'] = operation
        
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.RETRY,
            details=details,
            **kwargs
        )

class BusinessLogicError(ApplicationError):
    """Business logic error."""
    
    def __init__(self, message: str, rule: str = None, **kwargs):
        details = kwargs.pop('details', {})
        if rule:
            details['rule'] = rule
        
        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.MANUAL_INTERVENTION,
            details=details,
            **kwargs
        )

class ErrorHandler:
    """Central error handler for the application."""
    
    def __init__(self):
        self.error_stats: Dict[str, int] = {}
        self.recovery_attempts: Dict[str, int] = {}
    
    def handle_error(
        self, 
        error: Union[Exception, ApplicationError], 
        context: Optional[ErrorContext] = None
    ) -> ApplicationError:
        """Handle and classify errors."""
        
        if isinstance(error, ApplicationError):
            return error
        
        # Convert standard exceptions to ApplicationError
        app_error = self._convert_exception(error, context)
        
        # Update statistics
        self._update_error_stats(app_error)
        
        # Apply recovery strategy if applicable
        self._apply_recovery_strategy(app_error)
        
        return app_error
    
    def _convert_exception(self, error: Exception, context: Optional[ErrorContext]) -> ApplicationError:
        """Convert standard exceptions to ApplicationError."""
        
        error_mappings = {
            ValueError: (ErrorCategory.VALIDATION, ErrorSeverity.LOW, "VALIDATION_ERROR"),
            TypeError: (ErrorCategory.VALIDATION, ErrorSeverity.LOW, "TYPE_ERROR"),
            KeyError: (ErrorCategory.VALIDATION, ErrorSeverity.LOW, "KEY_ERROR"),
            FileNotFoundError: (ErrorCategory.NOT_FOUND, ErrorSeverity.MEDIUM, "FILE_NOT_FOUND"),
            PermissionError: (ErrorCategory.AUTHORIZATION, ErrorSeverity.HIGH, "PERMISSION_DENIED"),
            ConnectionError: (ErrorCategory.NETWORK, ErrorSeverity.HIGH, "CONNECTION_ERROR"),
            TimeoutError: (ErrorCategory.NETWORK, ErrorSeverity.HIGH, "TIMEOUT_ERROR"),
        }
        
        error_type = type(error)
        category, severity, error_code = error_mappings.get(
            error_type, 
            (ErrorCategory.SYSTEM, ErrorSeverity.HIGH, "UNKNOWN_ERROR")
        )
        
        return ApplicationError(
            message=str(error),
            error_code=error_code,
            category=category,
            severity=severity,
            context=context,
            cause=error
        )
    
    def _update_error_stats(self, error: ApplicationError) -> None:
        """Update error statistics."""
        key = f"{error.category.value}:{error.error_code}"
        self.error_stats[key] = self.error_stats.get(key, 0) + 1
    
    def _apply_recovery_strategy(self, error: ApplicationError) -> None:
        """Apply recovery strategy for the error."""
        
        if error.recovery_strategy == RecoveryStrategy.RETRY:
            retry_key = f"{error.error_code}:{error.context.resource_id}"
            retry_count = self.recovery_attempts.get(retry_key, 0)
            
            if retry_count < 3:  # Max 3 retries
                self.recovery_attempts[retry_key] = retry_count + 1
                logger.info(f"Scheduling retry for error {error.error_id}", extra={
                    "error_id": error.error_id,
                    "retry_count": retry_count + 1,
                    "max_retries": 3
                })
            else:
                logger.warning(f"Max retries exceeded for error {error.error_id}", extra={
                    "error_id": error.error_id,
                    "retry_count": retry_count
                })
        
        elif error.recovery_strategy == RecoveryStrategy.ESCALATE:
            logger.critical(f"Error requires escalation: {error.error_id}", extra={
                "error_id": error.error_id,
                "escalation_required": True
            })
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics."""
        total_errors = sum(self.error_stats.values())
        
        return {
            "total_errors": total_errors,
            "error_breakdown": dict(self.error_stats),
            "most_common_errors": sorted(
                self.error_stats.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10],
            "active_recovery_attempts": len(self.recovery_attempts)
        }

class RetryManager:
    """Manager for retry operations."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.retry_counts: Dict[str, int] = {}
    
    def should_retry(self, error: ApplicationError, operation_id: str) -> bool:
        """Determine if an operation should be retried."""
        
        if error.recovery_strategy != RecoveryStrategy.RETRY:
            return False
        
        retry_count = self.retry_counts.get(operation_id, 0)
        return retry_count < self.max_retries
    
    def record_retry(self, operation_id: str) -> int:
        """Record a retry attempt and return the retry count."""
        self.retry_counts[operation_id] = self.retry_counts.get(operation_id, 0) + 1
        return self.retry_counts[operation_id]
    
    def clear_retry_count(self, operation_id: str) -> None:
        """Clear retry count for successful operation."""
        self.retry_counts.pop(operation_id, None)
    
    def get_retry_delay(self, retry_count: int) -> float:
        """Calculate exponential backoff delay."""
        return self.base_delay * (2 ** (retry_count - 1))

class StatusRollbackManager:
    """Manager for rolling back status changes on failures."""
    
    def __init__(self):
        self.rollback_stack: List[Dict[str, Any]] = []
    
    def record_status_change(
        self, 
        resource_type: str, 
        resource_id: str, 
        old_status: str, 
        new_status: str,
        rollback_function: callable = None
    ) -> None:
        """Record a status change for potential rollback."""
        
        rollback_entry = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "old_status": old_status,
            "new_status": new_status,
            "rollback_function": rollback_function,
            "timestamp": datetime.utcnow()
        }
        
        self.rollback_stack.append(rollback_entry)
        
        logger.debug(f"Recorded status change for rollback", extra={
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status_change": f"{old_status} -> {new_status}"
        })
    
    async def rollback_on_error(self, error: ApplicationError) -> None:
        """Rollback status changes when an error occurs."""
        
        if error.recovery_strategy != RecoveryStrategy.ROLLBACK:
            return
        
        logger.info(f"Rolling back status changes due to error {error.error_id}")
        
        # Rollback in reverse order
        for rollback_entry in reversed(self.rollback_stack):
            try:
                if rollback_entry["rollback_function"]:
                    await rollback_entry["rollback_function"](
                        rollback_entry["resource_id"],
                        rollback_entry["old_status"]
                    )
                
                logger.info(f"Rolled back status change", extra={
                    "resource_type": rollback_entry["resource_type"],
                    "resource_id": rollback_entry["resource_id"],
                    "status_rollback": f"{rollback_entry['new_status']} -> {rollback_entry['old_status']}"
                })
                
            except Exception as rollback_error:
                logger.error(f"Failed to rollback status change", extra={
                    "resource_type": rollback_entry["resource_type"],
                    "resource_id": rollback_entry["resource_id"],
                    "rollback_error": str(rollback_error)
                })
        
        self.clear_rollback_stack()
    
    def clear_rollback_stack(self) -> None:
        """Clear the rollback stack after successful completion or rollback."""
        self.rollback_stack.clear()

def convert_to_http_exception(error: ApplicationError) -> HTTPException:
    """Convert ApplicationError to FastAPI HTTPException."""
    
    status_code_mapping = {
        ErrorCategory.VALIDATION: status.HTTP_400_BAD_REQUEST,
        ErrorCategory.AUTHENTICATION: status.HTTP_401_UNAUTHORIZED,
        ErrorCategory.AUTHORIZATION: status.HTTP_403_FORBIDDEN,
        ErrorCategory.NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCategory.CONFLICT: status.HTTP_409_CONFLICT,
        ErrorCategory.RATE_LIMIT: status.HTTP_429_TOO_MANY_REQUESTS,
        ErrorCategory.MAINTENANCE: status.HTTP_503_SERVICE_UNAVAILABLE,
    }
    
    status_code = status_code_mapping.get(error.category, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return HTTPException(
        status_code=status_code,
        detail={
            "error_id": error.error_id,
            "error_code": error.error_code,
            "message": error.user_message,
            "category": error.category.value,
            "timestamp": error.context.timestamp.isoformat(),
            "details": error.details if error.severity != ErrorSeverity.CRITICAL else {}
        },
        headers={"X-Error-ID": error.error_id}
    )

# Global instances
error_handler = ErrorHandler()
retry_manager = RetryManager()
rollback_manager = StatusRollbackManager()
