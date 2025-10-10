"""
API response formatting utilities.
"""
from typing import Any, Optional, Dict, List
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from datetime import datetime

from app.models import APIResponse, ErrorResponse, PaginatedResponse


class ResponseFormatter:
    """Utility class for formatting API responses consistently."""
    
    @staticmethod
    def success(
        data: Any = None,
        message: str = "Operation completed successfully",
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """
        Format successful API response.
        
        Args:
            data: Response data
            message: Success message
            status_code: HTTP status code
            headers: Additional headers
            
        Returns:
            JSONResponse: Formatted success response
        """
        response_data = APIResponse[Any](
            success=True,
            message=message,
            data=data
        )
        
        return JSONResponse(
            status_code=status_code,
            content=response_data.dict(),
            headers=headers or {}
        )
    
    @staticmethod
    def error(
        message: str,
        error_code: str = "ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """
        Format error API response.
        
        Args:
            message: Error message
            error_code: Error code identifier
            status_code: HTTP status code
            details: Additional error details
            headers: Additional headers
            
        Returns:
            JSONResponse: Formatted error response
        """
        response_data = ErrorResponse(
            success=False,
            message=message,
            error_code=error_code,
            details=details
        )
        
        return JSONResponse(
            status_code=status_code,
            content=response_data.dict(),
            headers=headers or {}
        )
    
    @staticmethod
    def paginated(
        items: List[Any],
        total: int,
        page: int,
        size: int,
        message: str = "Data retrieved successfully",
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """
        Format paginated API response.
        
        Args:
            items: List of items
            total: Total number of items
            page: Current page number
            size: Page size
            message: Success message
            status_code: HTTP status code
            headers: Additional headers
            
        Returns:
            JSONResponse: Formatted paginated response
        """
        paginated_data = PaginatedResponse.create(
            items=items,
            total=total,
            page=page,
            size=size
        )
        
        response_data = APIResponse[PaginatedResponse[Any]](
            success=True,
            message=message,
            data=paginated_data
        )
        
        return JSONResponse(
            status_code=status_code,
            content=response_data.dict(),
            headers=headers or {}
        )
    
    @staticmethod
    def created(
        data: Any,
        message: str = "Resource created successfully",
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """Format created resource response (201)."""
        return ResponseFormatter.success(
            data=data,
            message=message,
            status_code=201,
            headers=headers
        )
    
    @staticmethod
    def no_content(
        message: str = "Operation completed successfully",
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """Format no content response (204)."""
        return ResponseFormatter.success(
            data=None,
            message=message,
            status_code=204,
            headers=headers
        )
    
    @staticmethod
    def not_found(
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """Format not found response (404)."""
        return ResponseFormatter.error(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details,
            headers=headers
        )
    
    @staticmethod
    def unauthorized(
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """Format unauthorized response (401)."""
        return ResponseFormatter.error(
            message=message,
            error_code="UNAUTHORIZED",
            status_code=401,
            details=details,
            headers=headers
        )
    
    @staticmethod
    def forbidden(
        message: str = "Access forbidden",
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """Format forbidden response (403)."""
        return ResponseFormatter.error(
            message=message,
            error_code="FORBIDDEN",
            status_code=403,
            details=details,
            headers=headers
        )
    
    @staticmethod
    def validation_error(
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """Format validation error response (422)."""
        return ResponseFormatter.error(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=details,
            headers=headers
        )
    
    @staticmethod
    def internal_error(
        message: str = "Internal server error",
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """Format internal server error response (500)."""
        return ResponseFormatter.error(
            message=message,
            error_code="INTERNAL_ERROR",
            status_code=500,
            details=details,
            headers=headers
        )


class APIMetadata:
    """Utility class for adding metadata to API responses."""
    
    @staticmethod
    def add_request_metadata(
        request: Request,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add request metadata to response.
        
        Args:
            request: FastAPI request object
            response_data: Response data dictionary
            
        Returns:
            Dict: Response data with metadata
        """
        metadata = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": getattr(request.state, 'request_id', None),
            "path": str(request.url.path),
            "method": request.method
        }
        
        response_data["metadata"] = metadata
        return response_data
    
    @staticmethod
    def add_performance_metadata(
        response_data: Dict[str, Any],
        start_time: float
    ) -> Dict[str, Any]:
        """
        Add performance metadata to response.
        
        Args:
            response_data: Response data dictionary
            start_time: Request start time
            
        Returns:
            Dict: Response data with performance metadata
        """
        import time
        
        if "metadata" not in response_data:
            response_data["metadata"] = {}
        
        response_data["metadata"]["processing_time"] = f"{time.time() - start_time:.4f}s"
        return response_data
    
    @staticmethod
    def add_api_version(
        response_data: Dict[str, Any],
        version: str = "1.0.0"
    ) -> Dict[str, Any]:
        """
        Add API version to response metadata.
        
        Args:
            response_data: Response data dictionary
            version: API version
            
        Returns:
            Dict: Response data with version metadata
        """
        if "metadata" not in response_data:
            response_data["metadata"] = {}
        
        response_data["metadata"]["api_version"] = version
        return response_data


# Global response formatter instance
response_formatter = ResponseFormatter()
api_metadata = APIMetadata()

# Helper functions for OpenAPI documentation
def response_200(description: str = "Successful operation"):
    """OpenAPI response documentation for 200 status."""
    return {"description": description}

def response_400(description: str = "Bad request"):
    """OpenAPI response documentation for 400 status."""
    return {"description": description}

def response_401(description: str = "Authentication required"):
    """OpenAPI response documentation for 401 status."""
    return {"description": description}

def response_403(description: str = "Access forbidden"):
    """OpenAPI response documentation for 403 status."""
    return {"description": description}

def response_404(description: str = "Resource not found"):
    """OpenAPI response documentation for 404 status."""
    return {"description": description}

def response_422(description: str = "Validation error"):
    """OpenAPI response documentation for 422 status."""
    return {"description": description}

def response_500(description: str = "Internal server error"):
    """OpenAPI response documentation for 500 status."""
    return {"description": description}
