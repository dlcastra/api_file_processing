import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from httpx import AsyncClient


@pytest.mark.asyncio
class TestRegistrationEndpoint:
    """Test suite for the /registration endpoint with mocked dependencies"""

    @pytest.fixture
    def valid_user_data(self):
        """Fixture providing valid user registration data"""
        return {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123",
            "password1": "SecurePass123",
        }

    @pytest.fixture
    def mock_db(self):
        """Fixture providing a mocked database session"""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        return mock_session

    @pytest.fixture
    def mock_auth_service(self):
        """Fixture providing a mocked AuthService"""
        service = AsyncMock()
        service.register_user = AsyncMock()
        return service

    @patch("src.app.auth.routers.AuthService")
    @patch("src.app.auth.routers.PasswordValidator")
    async def test_successful_registration(
        self, mock_validator_class, mock_service_class, client: AsyncClient, valid_user_data, mock_auth_service
    ):
        """Test successful user registration with valid data"""
        mock_validator = MagicMock()
        mock_validator.password_validator.return_value = True
        mock_validator_class.return_value = mock_validator

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_auth_service.register_user.return_value = mock_user
        mock_service_class.return_value = mock_auth_service

        response = await client.post("/auth/registration", json=valid_user_data)

        assert response.status_code == 201
        assert response.json() == {"message": "Registration successfully completed"}
        mock_validator.password_validator.assert_called_once()
        mock_auth_service.register_user.assert_called_once()

    @patch("src.app.auth.routers.AuthService")
    @patch("src.app.auth.routers.PasswordValidator")
    async def test_registration_invalid_password(
        self, mock_validator_class, mock_service_class, client: AsyncClient, valid_user_data
    ):
        """Test registration fails when password validation fails"""
        mock_validator = MagicMock()
        mock_validator.password_validator.return_value = False
        mock_validator_class.return_value = mock_validator

        response = await client.post("/auth/registration", json=valid_user_data)

        assert response.status_code == 400
        assert "password" in response.json()["detail"]

    @patch("src.app.auth.routers.AuthService")
    @patch("src.app.auth.routers.PasswordValidator")
    async def test_registration_duplicate_email(
        self, mock_validator_class, mock_service_class, client: AsyncClient, valid_user_data, mock_auth_service
    ):
        """Test registration fails when email already exists"""
        mock_validator = MagicMock()
        mock_validator.password_validator.return_value = True
        mock_validator_class.return_value = mock_validator

        mock_auth_service.register_user.side_effect = HTTPException(status_code=400, detail="User already exists")
        mock_service_class.return_value = mock_auth_service

        response = await client.post("/auth/registration", json=valid_user_data)

        assert response.status_code == 400
        assert response.json()["detail"] == "User already exists"

    @patch("src.app.auth.routers.AuthService")
    @patch("src.app.auth.routers.PasswordValidator")
    async def test_registration_database_error(
        self, mock_validator_class, mock_service_class, client: AsyncClient, valid_user_data, mock_auth_service
    ):
        """Test registration handles database errors gracefully"""
        mock_validator = MagicMock()
        mock_validator.password_validator.return_value = True
        mock_validator_class.return_value = mock_validator

        mock_auth_service.register_user.side_effect = Exception("Database connection failed")
        mock_service_class.return_value = mock_auth_service

        response = await client.post("/auth/registration", json=valid_user_data)

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal Server Error"

    async def test_registration_missing_username(self, client: AsyncClient):
        """Test registration fails when username is missing"""
        incomplete_data = {
            "email": "test@example.com",
            "password": "SecurePass123",
            "password1": "SecurePass123",  # Add this
        }
        response = await client.post("/auth/registration", json=incomplete_data)

        assert response.status_code == 422

    async def test_registration_missing_email(self, client: AsyncClient):
        """Test registration fails when email is missing"""
        incomplete_data = {
            "username": "testuser",
            "password": "SecurePass123",
            "password1": "SecurePass123",  # Add this
        }
        response = await client.post("/auth/registration", json=incomplete_data)

        assert response.status_code == 422

    async def test_registration_missing_password(self, client: AsyncClient):
        """Test registration fails when password is missing"""
        incomplete_data = {"username": "testuser", "email": "test@example.com"}
        response = await client.post("/auth/registration", json=incomplete_data)

        assert response.status_code == 422

    async def test_registration_invalid_email_format(self, client: AsyncClient):
        """Test registration fails with invalid email format"""
        invalid_data = {
            "username": "testuser",
            "email": "invalid-email",
            "password": "SecurePass123",
            "password1": "SecurePass123",
        }
        response = await client.post("/auth/registration", json=invalid_data)

        assert response.status_code == 422

    async def test_registration_empty_username(self, client: AsyncClient):
        """Test registration fails with empty username"""
        invalid_data = {
            "username": "",
            "email": "test@example.com",
            "password": "SecurePass123",
            "password1": "SecurePass123",  # Add this
        }
        response = await client.post("/auth/registration", json=invalid_data)

        assert response.status_code == 422
