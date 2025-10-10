"""
Custom middleware for the FastAPI application.
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.models import ErrorResponse

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware for detailed request and response logging."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.sensitive_headers = {
            "authorization", "cookie", "x-api-key", "x-auth-token"
        }
        self.sensitive_paths = {
            "/auth/login", "/auth/register", "/users/change-password", 
            "/users/reset-password"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log detailed request and response information."""
        start_time = time.time()
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Extract request details
        client_ip = request.client.host if request.client else 'unknown'
        user_agent = request.headers.get('user-agent', 'unknown')
        content_length = request.headers.get('content-length', '0')
        
        # Log detailed request information
        logger.info(
            f"Request [{request_id}]: {request.method} {request.url.path} "
            f"from {client_ip} | UA: {user_agent[:50]}... | "
            f"Content-Length: {content_length}"
        )
        
        # Log query parameters (if any)
        if request.query_params:
            logger.debug(f"Query params [{request_id}]: {dict(request.query_params)}")
        
        # Log headers (excluding sensitive ones)
        if logger.isEnabledFor(logging.DEBUG):
            safe_headers = {
                k: v if k.lower() not in self.sensitive_headers else "[REDACTED]"
                for k, v in request.headers.items()
            }
            logger.debug(f"Headers [{request_id}]: {safe_headers}")
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        # Log detailed response information
        logger.log(
            log_level,
            f"Response [{request_id}]: {response.status_code} "
            f"for {request.method} {request.url.path} | "
            f"Time: {process_time:.4f}s | "
            f"Size: {response.headers.get('content-length', 'unknown')} bytes"
        )
        
        # Log response headers for debugging
        if logger.isEnabledFor(logging.DEBUG) and response.status_code >= 400:
            logger.debug(f"Response headers [{request_id}]: {dict(response.headers)}")
        
        # Add processing time and request ID headers
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        if not response.headers.get("X-Request-ID"):
            response.headers["X-Request-ID"] = request_id
        
        # Log slow requests
        if process_time > 1.0:  # Log requests taking more than 1 second
            logger.warning(
                f"Slow request [{request_id}]: {request.method} {request.url.path} "
                f"took {process_time:.4f}s"
            )
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware for handling and formatting errors."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle and format errors consistently with detailed logging."""
        request_id = self._generate_request_id()
        
        try:
            # Add request ID to request state for tracking
            request.state.request_id = request_id
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
        
        except HTTPException as e:
            # Enhanced HTTPException handling with request context
            logger.warning(
                f"HTTP Exception [{request_id}]: {e.status_code} - {e.detail} "
                f"for {request.method} {request.url.path}"
            )
            
            # Add request ID to error response
            if hasattr(e, 'headers') and e.headers:
                e.headers["X-Request-ID"] = request_id
            else:
                e.headers = {"X-Request-ID": request_id}
            
            raise e
        
        except ValueError as e:
            # Handle validation errors with context
            logger.warning(
                f"Validation error [{request_id}]: {e} "
                f"for {request.method} {request.url.path}"
            )
            error_response = ErrorResponse(
                success=False,
                message=str(e),
                error_code="VALIDATION_ERROR",
                details={
                    "request_id": request_id,
                    "path": str(request.url.path),
                    "method": request.method
                }
            )
            return JSONResponse(
                status_code=400,
                content=error_response.dict(),
                headers={"X-Request-ID": request_id}
            )
        
        except PermissionError as e:
            # Handle permission errors with context
            logger.warning(
                f"Permission error [{request_id}]: {e} "
                f"for {request.method} {request.url.path}"
            )
            error_response = ErrorResponse(
                success=False,
                message="Permission denied",
                error_code="PERMISSION_DENIED",
                details={
                    "request_id": request_id,
                    "path": str(request.url.path),
                    "method": request.method
                }
            )
            return JSONResponse(
                status_code=403,
                content=error_response.dict(),
                headers={"X-Request-ID": request_id}
            )
        
        except ConnectionError as e:
            # Handle database/external service connection errors
            logger.error(
                f"Connection error [{request_id}]: {e} "
                f"for {request.method} {request.url.path}"
            )
            error_response = ErrorResponse(
                success=False,
                message="Service temporarily unavailable",
                error_code="CONNECTION_ERROR",
                details={
                    "request_id": request_id,
                    "path": str(request.url.path),
                    "method": request.method
                }
            )
            return JSONResponse(
                status_code=503,
                content=error_response.dict(),
                headers={"X-Request-ID": request_id}
            )
        
        except TimeoutError as e:
            # Handle timeout errors
            logger.error(
                f"Timeout error [{request_id}]: {e} "
                f"for {request.method} {request.url.path}"
            )
            error_response = ErrorResponse(
                success=False,
                message="Request timeout",
                error_code="TIMEOUT_ERROR",
                details={
                    "request_id": request_id,
                    "path": str(request.url.path),
                    "method": request.method
                }
            )
            return JSONResponse(
                status_code=408,
                content=error_response.dict(),
                headers={"X-Request-ID": request_id}
            )
        
        except Exception as e:
            # Handle unexpected errors with full context
            logger.error(
                f"Unexpected error [{request_id}]: {e} "
                f"for {request.method} {request.url.path}",
                exc_info=True
            )
            error_response = ErrorResponse(
                success=False,
                message="Internal server error",
                error_code="INTERNAL_ERROR",
                details={
                    "request_id": request_id,
                    "path": str(request.url.path),
                    "method": request.method
                }
            )
            return JSONResponse(
                status_code=500,
                content=error_response.dict(),
                headers={"X-Request-ID": request_id}
            )
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID for tracking."""
        import uuid
        return str(uuid.uuid4())[:8]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to responses."""
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Add HSTS header for HTTPS (only in production)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Basic rate limiting middleware (placeholder implementation).
    
    In production, you would use a more sophisticated rate limiting solution
    like Redis-based rate limiting or a service like CloudFlare.
    """
    
    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}  # In production, use Redis or similar
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting (placeholder implementation)."""
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # For now, just log the request (implement actual rate limiting logic here)
        logger.debug(f"Rate limit check for {client_ip}")
        
        # In a real implementation, you would:
        # 1. Check request count for this IP in the last minute
        # 2. If over limit, return 429 Too Many Requests
        # 3. Otherwise, increment counter and proceed
        
        response = await call_next(request)
        return response


def setup_middleware(app):
    """Set up all middleware for the application."""
    # Add middleware in reverse order (last added is executed first)
    
    # Security headers (outermost)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Error handling
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Request/response logging
    app.add_middleware(LoggingMiddleware)
    
    # Rate limiting (if needed)
    # app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
    
    logger.info("Middleware setup completed")
