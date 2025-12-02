from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestLoginEndpoint:
    """Test suite for the /login endpoint with mocked dependencies"""

    @pytest.fixture
    def valid_login_data(self):
        """Fixture providing valid user login data"""
        return {"username": "testuser", "password": "SecurePass123", "totp_code": None}

    @pytest.fixture
    def valid_login_data_with_2fa(self):
        """Fixture providing valid user login data with 2FA code"""
        return {
            "username": "testuser",
            "password": "SecurePass123",
            "totp_code": "123456",
        }

    @pytest.fixture
    def mock_user(self):
        """Fixture providing a mocked User object"""
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        user.is_2fa_enabled = False
        user.totp_secret = None
        user.last_login = None
        return user

    @pytest.fixture
    def mock_user_with_2fa(self):
        """Fixture providing a mocked User object with 2FA enabled"""
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        user.is_2fa_enabled = True
        user.totp_secret = "JBSWY3DPEHPK3PXP"
        user.last_login = None
        return user

    @pytest.fixture
    def mock_auth_service(self):
        """Fixture providing a mocked AuthService"""
        service = AsyncMock()
        service.authenticate_user = AsyncMock()
        return service

    @patch("src.app.auth.routers.AuthService")
    async def test_login_invalid_credentials(self, mock_service_class, client: AsyncClient, valid_login_data):
        """Test login fails with invalid username or password"""
        mock_auth_service = AsyncMock()
        mock_auth_service.authenticate_user.return_value = None
        mock_service_class.return_value = mock_auth_service

        response = await client.post("/auth/login", json=valid_login_data)

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid username or password"

    @patch("src.app.auth.routers.pyotp")
    @patch("src.app.auth.routers.AuthService")
    async def test_login_invalid_2fa_code(
        self, mock_service_class, mock_pyotp, client: AsyncClient, valid_login_data_with_2fa, mock_user_with_2fa
    ):
        """Test login fails with invalid 2FA code"""
        mock_auth_service = AsyncMock()
        mock_auth_service.authenticate_user.return_value = mock_user_with_2fa
        mock_service_class.return_value = mock_auth_service

        mock_totp = MagicMock()
        mock_totp.verify.return_value = False
        mock_pyotp.TOTP.return_value = mock_totp

        response = await client.post("/auth/login", json=valid_login_data_with_2fa)

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid 2FA code"

    async def test_login_missing_username(self, client: AsyncClient):
        """Test login fails when username is missing"""
        incomplete_data = {
            "password": "SecurePass123",
        }
        response = await client.post("/auth/login", json=incomplete_data)

        assert response.status_code == 422

    async def test_login_missing_password(self, client: AsyncClient):
        """Test login fails when password is missing"""
        incomplete_data = {
            "username": "testuser",
        }
        response = await client.post("/auth/login", json=incomplete_data)

        assert response.status_code == 422

    async def test_login_empty_username(self, client: AsyncClient):
        """Test login fails with empty username"""
        invalid_data = {
            "username": "",
            "password": "SecurePass123",
        }
        response = await client.post("/auth/login", json=invalid_data)

        assert response.status_code == 422

    async def test_login_empty_password(self, client: AsyncClient):
        """Test login fails with empty password"""
        invalid_data = {
            "username": "testuser",
            "password": "",
        }
        response = await client.post("/auth/login", json=invalid_data)

        assert response.status_code == 422
