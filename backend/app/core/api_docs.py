"""
API documentation configuration and utilities.
"""
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema with enhanced documentation.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        Dict: Custom OpenAPI schema
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Manuscript Processor API",
        version="1.0.0",
        description="""
        ## Manuscript Processor API
        
        A comprehensive API for processing PDF manuscripts and converting them to Word documents.
        
        ### Features
        - **User Authentication**: JWT-based authentication with secure token management
        - **User Management**: Profile management, password reset, admin controls
        - **File Processing**: PDF to Word conversion with S3 storage
        - **Activity Logging**: Comprehensive audit trail for all user actions
        - **Admin Dashboard**: User statistics and system monitoring
        
        ### Authentication
        Most endpoints require authentication. Include the JWT token in the Authorization header:
        ```
        Authorization: Bearer <your-jwt-token>
        ```
        
        ### API Versioning
        This API supports versioning. You can access specific versions using:
        - `/v1/` prefix for version 1 endpoints
        - Root level endpoints for backward compatibility
        
        ### Error Handling
        All errors follow a consistent format:
        ```json
        {
          "success": false,
          "message": "Error description",
          "error_code": "ERROR_TYPE",
          "details": {
            "request_id": "abc123",
            "path": "/api/endpoint",
            "method": "POST"
          }
        }
        ```
        
        ### Rate Limiting
        API endpoints are rate-limited to prevent abuse:
        - Authentication endpoints: 10 requests per minute
        - Regular API endpoints: 60 requests per minute
        
        ### Request Tracking
        Each request is assigned a unique ID for tracking and debugging.
        The ID is returned in the `X-Request-ID` header.
        """,
        routes=app.routes,
        servers=[
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            },
            {
                "url": "https://api.manuscript-processor.com",
                "description": "Production server"
            }
        ]
    )
    
    # Add custom tags for better organization
    openapi_schema["tags"] = [
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints"
        },
        {
            "name": "User Management",
            "description": "User profile and account management endpoints"
        },
        {
            "name": "Manuscripts",
            "description": "Manuscript upload, processing, and download endpoints"
        },
        {
            "name": "Admin",
            "description": "Administrative endpoints for user and system management"
        },
        {
            "name": "Health Check",
            "description": "System health and status endpoints"
        }
    ]
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token obtained from /auth/login endpoint"
        }
    }
    
    # Add common response schemas
    openapi_schema["components"]["schemas"].update({
        "APIResponse": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "description": "Whether the request was successful"
                },
                "message": {
                    "type": "string",
                    "description": "Response message"
                },
                "data": {
                    "description": "Response data (varies by endpoint)"
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string", "format": "date-time"},
                        "request_id": {"type": "string"},
                        "processing_time": {"type": "string"},
                        "api_version": {"type": "string"}
                    }
                }
            },
            "required": ["success", "message"]
        },
        "ErrorResponse": {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": False
                },
                "message": {
                    "type": "string",
                    "description": "Error message"
                },
                "error_code": {
                    "type": "string",
                    "description": "Error code identifier"
                },
                "details": {
                    "type": "object",
                    "description": "Additional error details"
                }
            },
            "required": ["success", "message", "error_code"]
        }
    })
    
    # Add common examples
    openapi_schema["components"]["examples"] = {
        "SuccessResponse": {
            "summary": "Successful API response",
            "value": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123", "name": "example"},
                "metadata": {
                    "timestamp": "2025-09-13T14:30:00Z",
                    "request_id": "abc123",
                    "processing_time": "0.0234s",
                    "api_version": "1.0.0"
                }
            }
        },
        "ErrorResponse": {
            "summary": "Error API response",
            "value": {
                "success": False,
                "message": "Validation failed",
                "error_code": "VALIDATION_ERROR",
                "details": {
                    "request_id": "abc123",
                    "path": "/api/endpoint",
                    "method": "POST"
                }
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def setup_api_docs(app: FastAPI) -> None:
    """
    Set up API documentation configuration.
    
    Args:
        app: FastAPI application instance
    """
    # Set custom OpenAPI schema generator
    app.openapi = lambda: custom_openapi_schema(app)
    
    # Configure Swagger UI
    app.swagger_ui_parameters = {
        "deepLinking": True,
        "displayRequestDuration": True,
        "docExpansion": "none",
        "operationsSorter": "method",
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "tryItOutEnabled": True
    }


def get_api_info() -> Dict[str, Any]:
    """
    Get API information for health checks and status endpoints.
    
    Returns:
        Dict: API information
    """
    return {
        "name": "Manuscript Processor API",
        "version": "1.0.0",
        "description": "API for processing PDF manuscripts and converting them to Word documents",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json"
        },
        "endpoints": {
            "authentication": [
                "POST /auth/register",
                "POST /auth/login",
                "POST /auth/logout",
                "GET /auth/me",
                "POST /auth/refresh",
                "GET /auth/validate"
            ],
            "user_management": [
                "GET /users/profile",
                "PUT /users/profile",
                "POST /users/change-password",
                "POST /users/request-password-reset",
                "POST /users/reset-password",
                "GET /users/activities"
            ],
            "admin": [
                "GET /users/admin/list",
                "PUT /users/admin/{user_id}",
                "GET /users/admin/statistics",
                "GET /users/admin/activities"
            ]
        },
        "features": [
            "JWT Authentication",
            "User Profile Management",
            "Password Reset",
            "Activity Logging",
            "Admin Dashboard",
            "API Versioning",
            "Request Tracking",
            "Error Handling",
            "Rate Limiting"
        ]
    }


# Error code documentation
ERROR_CODES = {
    "VALIDATION_ERROR": {
        "description": "Input validation failed",
        "status_code": 400,
        "example": "Email format is invalid"
    },
    "UNAUTHORIZED": {
        "description": "Authentication required",
        "status_code": 401,
        "example": "JWT token is missing or invalid"
    },
    "FORBIDDEN": {
        "description": "Access denied",
        "status_code": 403,
        "example": "Admin access required"
    },
    "NOT_FOUND": {
        "description": "Resource not found",
        "status_code": 404,
        "example": "User not found"
    },
    "TIMEOUT_ERROR": {
        "description": "Request timeout",
        "status_code": 408,
        "example": "Database query timed out"
    },
    "INTERNAL_ERROR": {
        "description": "Internal server error",
        "status_code": 500,
        "example": "Unexpected server error occurred"
    },
    "CONNECTION_ERROR": {
        "description": "External service unavailable",
        "status_code": 503,
        "example": "Database connection failed"
    }
}
