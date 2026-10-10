import logging
from datetime import datetime, timezone

from .config import AuthSettings
from .constants import ALLOWED_ROLES, ROLE_ADMIN, ROLE_USER
from .exceptions import (
    AccountDeactivatedError,
    AccountLockedError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
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
        if user is None or not valid_password:
            if user is not None:
                self._repository.increment_failed_login(
                    user.username,
                    self._settings.login_lockout_max_attempts,
                    self._settings.login_lockout_duration_minutes,
                )
            logger.warning("Failed login attempt for user: %s", canonical_username)
            raise AuthenticationError("Invalid username or password.")

        # Check lockout after verifying the password to avoid leaking account existence
        if user.locked_until is not None and user.locked_until > datetime.now(timezone.utc):
            logger.warning("Login blocked — account locked: %s", canonical_username)
            raise AccountLockedError(
                "Account is temporarily locked due to too many failed attempts. "
                "Please try again later."
            )

        if not user.is_active:
            logger.warning("Login attempt for deactivated user: %s", canonical_username)
            raise AccountDeactivatedError(
                "Your account has been deactivated. Please contact an administrator."
            )

        self._repository.reset_failed_login(user.username)
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

        password_hash = self._password_hasher.hash_password(password)
        result = self._repository.create_user(
            username=canonical_username,
            password_hash=password_hash,
            role=role,
        )
        logger.info("User created: %s (role=%s)", canonical_username, role)
        return result


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
        logger.info("Password updated for user: %s", canonical_username)

    def set_user_active(self, username: str, active: bool) -> None:
        """Activate or deactivate a user account.

        Args:
            username (str): Raw username of the account to update.
            active (bool): True to activate, False to deactivate.

        Raises:
            UserNotFoundError: If the user does not exist.
            AuthorizationError: If the target user has the admin role.
        """
        canonical_username = normalize_username(username)
        user = self._repository.get_by_username(canonical_username)
        if user is None:
            raise UserNotFoundError("User does not exist.")
        if user.role == ROLE_ADMIN:
            raise AuthorizationError("Admin accounts cannot be deactivated.")
        self._repository.set_active(canonical_username, active)
        logger.info("User %s set active=%s", canonical_username, active)

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
        logger.info("User deleted: %s", canonical_username)
