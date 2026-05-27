import logging

from .config import AuthSettings
from .constants import ALLOWED_ROLES, ROLE_ADMIN, ROLE_USER
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    UserAlreadyExistsError,
    UserNotFoundError,
    ValidationError,
)
from .models import UserRecord, UserSummary
from .protocols import UserRepositoryProtocol
from .security import PasswordHasher, normalize_username, validate_password_strength

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Handles user authentication and initial admin bootstrap.

    Args:
        repository (UserRepositoryProtocol): Data-access layer for user records.
        password_hasher (PasswordHasher): bcrypt hasher for creating/verifying hashes.
        settings (AuthSettings): Application auth configuration.
    """

    def __init__(
        self,
        repository: UserRepositoryProtocol,
        password_hasher: PasswordHasher,
        settings: AuthSettings,
    ):
        """Initialise the authentication service.

        Args:
            repository (UserRepositoryProtocol): Data-access layer for user records.
            password_hasher (PasswordHasher): bcrypt hasher for creating and verifying hashes.
            settings (AuthSettings): Application auth configuration.
        """
        self._repository = repository
        self._password_hasher = password_hasher
        self._settings = settings

    def bootstrap_admin_user(self) -> None:
        """Create the default admin user on first startup if it does not exist yet.

        Reads `ADMIN_USERNAME` and `ADMIN_PASSWORD` from settings. No-op if auth is
        disabled or the admin already exists.

        Raises:
            ConfigurationError: If the username/password env vars are missing or the
                existing user has a non-admin role.
        """
        if not self._settings.enabled:
            return

        admin_username = self._settings.admin_username
        admin_password = self._settings.admin_password
        if not admin_username or not admin_password:
            raise ConfigurationError("ADMIN_USERNAME and ADMIN_PASSWORD must be set.")

        canonical_admin_username = normalize_username(admin_username)
        existing_admin = self._repository.get_by_username(canonical_admin_username)
        if existing_admin:
            if existing_admin.role != ROLE_ADMIN:
                raise ConfigurationError(
                    "Configured ADMIN_USERNAME exists but is not assigned admin role."
                )
            return

        validate_password_strength(admin_password, self._settings)
        password_hash = self._password_hasher.hash_password(admin_password)
        self._repository.create_user(
            username=canonical_admin_username,
            password_hash=password_hash,
            role=ROLE_ADMIN,
        )

    def authenticate(self, username: str, password: str) -> UserRecord:
        """Verify credentials and return the user record on success.

        Always performs a bcrypt check (even for unknown users) to prevent timing attacks.

        Args:
            username (str): Raw username from the login form.
            password (str): Plain-text password attempt.

        Returns:
            UserRecord: Authenticated, active user.

        Raises:
            AuthenticationError: On invalid credentials, unknown user, or inactive account.
        """
        if not password:
            self._password_hasher.verify_password_with_fallback("", None)
            raise AuthenticationError("Invalid username or password.")

        try:
            canonical_username = normalize_username(username)
        except ValidationError:
            self._password_hasher.verify_password_with_fallback(password, None)
            raise AuthenticationError("Invalid username or password.")

        user = self._repository.get_by_username(canonical_username)
        stored_hash = user.password_hash if user else None
        valid_password = self._password_hasher.verify_password_with_fallback(
            password,
            stored_hash,
        )
        if user is None or not valid_password or not user.is_active:
            logger.warning("Failed login attempt for user: %s", canonical_username)
            raise AuthenticationError("Invalid username or password.")
        logger.info("User logged in: %s", canonical_username)
        return user

    def create_user(self, username: str, password: str, role: str = ROLE_USER) -> UserRecord:
        """Create a new user after validating role, username, and password strength.

        Args:
            username (str): Desired username (4-16 alphanumeric/underscore/hyphen chars).
            password (str): Plain-text password (must meet minimum length).
            role (str, default=ROLE_USER): Assigned role (`"user"` or `"admin"`).

        Returns:
            UserRecord: The newly created user record.

        Raises:
            ValidationError: Invalid role, username format, or password strength.
            UserAlreadyExistsError: If the username is already taken.
        """
        if role not in ALLOWED_ROLES:
            raise ValidationError("Invalid role.")
        canonical_username = normalize_username(username)
        validate_password_strength(password, self._settings)

        existing_user = self._repository.get_by_username(canonical_username)
        if existing_user:
            raise UserAlreadyExistsError("Username already exists.")

        password_hash = self._password_hasher.hash_password(password)
        return self._repository.create_user(
            username=canonical_username,
            password_hash=password_hash,
            role=role,
        )


class UserManagementService:
    """Admin-facing service for listing users, updating passwords, and deleting accounts.

    Args:
        repository (UserRepositoryProtocol): Data-access layer for user records.
        password_hasher (PasswordHasher): bcrypt hasher used when updating passwords.
        settings (AuthSettings): Application auth configuration.
    """

    def __init__(
        self,
        repository: UserRepositoryProtocol,
        password_hasher: PasswordHasher,
        settings: AuthSettings,
    ):
        """Initialise the user management service.

        Args:
            repository (UserRepositoryProtocol): Data-access layer for user records.
            password_hasher (PasswordHasher): bcrypt hasher used when updating passwords.
            settings (AuthSettings): Application auth configuration.
        """
        self._repository = repository
        self._password_hasher = password_hasher
        self._settings = settings

    def list_users(self) -> list[UserSummary]:
        """Return all users as public summaries (no password hashes).

        Returns:
            list[UserSummary]: Users sorted alphabetically by username.
        """
        return self._repository.list_users()

    def update_password(self, username: str, new_password: str) -> None:
        """Change a user's password after validating strength.

        Args:
            username (str): Raw username of the account to update.
            new_password (str): New plain-text password (must meet minimum length).

        Raises:
            ValidationError: If the new password is too short or too long.
            UserNotFoundError: If the username does not exist.
        """
        canonical_username = normalize_username(username)
        validate_password_strength(new_password, self._settings)
        password_hash = self._password_hasher.hash_password(new_password)
        self._repository.update_password_hash(
            username=canonical_username,
            password_hash=password_hash,
        )

    def delete_user(self, username: str) -> None:
        """Delete a non-admin user account.

        Args:
            username (str): Raw username of the account to delete.

        Raises:
            UserNotFoundError: If the user does not exist.
            AuthorizationError: If the target user has the admin role.
        """
        canonical_username = normalize_username(username)
        user = self._repository.get_by_username(canonical_username)
        if user is None:
            raise UserNotFoundError("User does not exist.")
        if user.role == ROLE_ADMIN:
            raise AuthorizationError("Admin users cannot be deleted.")
        self._repository.delete_user(canonical_username)
