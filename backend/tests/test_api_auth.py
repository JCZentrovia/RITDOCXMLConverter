"""
Unit tests for authentication API endpoints.

This module tests user registration, login, logout, password reset,
and token validation functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient

from app.core.security import create_access_token, verify_password
from app.models.user import UserCreate, UserInDB
from app.services.user_service import user_service

pytestmark = pytest.mark.asyncio

class TestAuthEndpoints:
    """Test authentication API endpoints."""
    
    async def test_register_user_success(self, async_client: AsyncClient, test_data_factory):
        """Test successful user registration."""
        user_data = test_data_factory.user_create_data()
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": user_data.email,
                "password": user_data.password,
                "full_name": user_data.full_name
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
        assert "data" in data
        assert "user" in data["data"]
        assert "access_token" in data["data"]
        
        user = data["data"]["user"]
        assert user["email"] == user_data.email
        assert user["full_name"] == user_data.full_name
        assert "password" not in user  # Password should not be returned
        assert "id" in user
        assert user["is_active"] is True
    
    async def test_register_user_duplicate_email(self, async_client: AsyncClient, test_user: UserInDB):
        """Test registration with duplicate email."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "newpassword123",
                "full_name": "New User"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert "already registered" in data["detail"].lower()
    
    async def test_register_user_invalid_email(self, async_client: AsyncClient):
        """Test registration with invalid email."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "password123",
                "full_name": "Test User"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_register_user_weak_password(self, async_client: AsyncClient):
        """Test registration with weak password."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "123",  # Too short
                "full_name": "Test User"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_login_success(self, async_client: AsyncClient, test_user: UserInDB):
        """Test successful login."""
        response = await async_client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword123"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "access_token" in data["data"]
        assert "token_type" in data["data"]
        assert "user" in data["data"]
        
        assert data["data"]["token_type"] == "bearer"
        
        user = data["data"]["user"]
        assert user["email"] == test_user.email
        assert user["full_name"] == test_user.full_name
        assert "password" not in user
    
    async def test_login_invalid_credentials(self, async_client: AsyncClient, test_user: UserInDB):
        """Test login with invalid credentials."""
        response = await async_client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "wrongpassword"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["success"] is False
    
    async def test_login_nonexistent_user(self, async_client: AsyncClient):
        """Test login with nonexistent user."""
        response = await async_client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "password123"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["success"] is False
    
    async def test_get_current_user_success(self, async_client: AsyncClient, auth_headers: dict, test_user: UserInDB):
        """Test getting current user with valid token."""
        response = await async_client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        user = data["data"]
        assert user["email"] == test_user.email
        assert user["full_name"] == test_user.full_name
        assert "password" not in user
    
    async def test_get_current_user_invalid_token(self, async_client: AsyncClient):
        """Test getting current user with invalid token."""
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_get_current_user_no_token(self, async_client: AsyncClient):
        """Test getting current user without token."""
        response = await async_client.get("/api/v1/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_logout_success(self, async_client: AsyncClient, auth_headers: dict):
        """Test successful logout."""
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
    
    async def test_logout_no_token(self, async_client: AsyncClient):
        """Test logout without token."""
        response = await async_client.post("/api/v1/auth/logout")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('app.services.user_service.send_password_reset_email')
    async def test_request_password_reset_success(self, mock_send_email, async_client: AsyncClient, test_user: UserInDB):
        """Test successful password reset request."""
        mock_send_email.return_value = True
        
        response = await async_client.post(
            "/api/v1/auth/request-password-reset",
            json={"email": test_user.email}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
        mock_send_email.assert_called_once()
    
    async def test_request_password_reset_nonexistent_user(self, async_client: AsyncClient):
        """Test password reset request for nonexistent user."""
        response = await async_client.post(
            "/api/v1/auth/request-password-reset",
            json={"email": "nonexistent@example.com"}
        )
        
        # Should return success even for nonexistent users (security)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
    
    async def test_reset_password_success(self, async_client: AsyncClient, test_user: UserInDB):
        """Test successful password reset."""
        # Create reset token
        reset_token = create_access_token(
            data={"sub": test_user.email, "type": "password_reset"},
            expires_delta=timedelta(hours=1)
        )
        
        new_password = "newpassword123"
        
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": new_password
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
        
        # Verify password was changed
        updated_user = await user_service.get_user_by_email(test_user.email)
        assert verify_password(new_password, updated_user.hashed_password)
    
    async def test_reset_password_invalid_token(self, async_client: AsyncClient):
        """Test password reset with invalid token."""
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "invalid_token",
                "new_password": "newpassword123"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
    
    async def test_reset_password_expired_token(self, async_client: AsyncClient, test_user: UserInDB):
        """Test password reset with expired token."""
        # Create expired token
        expired_token = create_access_token(
            data={"sub": test_user.email, "type": "password_reset"},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": expired_token,
                "new_password": "newpassword123"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
    
    async def test_change_password_success(self, async_client: AsyncClient, auth_headers: dict, test_user: UserInDB):
        """Test successful password change."""
        new_password = "newpassword456"
        
        response = await async_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "testpassword123",
                "new_password": new_password
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
        
        # Verify password was changed
        updated_user = await user_service.get_user_by_email(test_user.email)
        assert verify_password(new_password, updated_user.hashed_password)
    
    async def test_change_password_wrong_current_password(self, async_client: AsyncClient, auth_headers: dict):
        """Test password change with wrong current password."""
        response = await async_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "wrongpassword",
                "new_password": "newpassword456"
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
    
    async def test_change_password_no_auth(self, async_client: AsyncClient):
        """Test password change without authentication."""
        response = await async_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "testpassword123",
                "new_password": "newpassword456"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

class TestTokenValidation:
    """Test token validation and security."""
    
    async def test_token_expiration(self, async_client: AsyncClient, test_user: UserInDB):
        """Test that expired tokens are rejected."""
        # Create expired token
        expired_token = create_access_token(
            data={"sub": test_user.email, "user_id": str(test_user.id)},
            expires_delta=timedelta(seconds=-1)
        )
        
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_token_with_invalid_user_id(self, async_client: AsyncClient):
        """Test token with invalid user ID."""
        token = create_access_token(
            data={"sub": "test@example.com", "user_id": "invalid_user_id"}
        )
        
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_token_without_user_id(self, async_client: AsyncClient):
        """Test token without user_id claim."""
        token = create_access_token(
            data={"sub": "test@example.com"}  # Missing user_id
        )
        
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_malformed_token(self, async_client: AsyncClient):
        """Test malformed JWT token."""
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer malformed.token.here"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_missing_bearer_prefix(self, async_client: AsyncClient, test_user: UserInDB):
        """Test token without Bearer prefix."""
        token = create_access_token(
            data={"sub": test_user.email, "user_id": str(test_user.id)}
        )
        
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": token}  # Missing "Bearer "
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
