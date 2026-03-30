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


class AuthenticationService:
    def __init__(
        self,
        repository: UserRepositoryProtocol,
        password_hasher: PasswordHasher,
        settings: AuthSettings,
    ):
        self._repository = repository
        self._password_hasher = password_hasher
        self._settings = settings

    def bootstrap_admin_user(self) -> None:
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
            raise AuthenticationError("Invalid username or password.")
        return user

    def create_user(self, username: str, password: str, role: str = ROLE_USER) -> UserRecord:
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
    def __init__(
        self,
        repository: UserRepositoryProtocol,
        password_hasher: PasswordHasher,
        settings: AuthSettings,
    ):
        self._repository = repository
        self._password_hasher = password_hasher
        self._settings = settings

    def list_users(self) -> list[UserSummary]:
        return self._repository.list_users()

    def update_password(self, username: str, new_password: str) -> None:
        canonical_username = normalize_username(username)
        validate_password_strength(new_password, self._settings)
        password_hash = self._password_hasher.hash_password(new_password)
        self._repository.update_password_hash(
            username=canonical_username,
            password_hash=password_hash,
        )

    def delete_user(self, username: str) -> None:
        canonical_username = normalize_username(username)
        user = self._repository.get_by_username(canonical_username)
        if user is None:
            raise UserNotFoundError("User does not exist.")
        if user.role == ROLE_ADMIN:
            raise AuthorizationError("Admin users cannot be deleted.")
        self._repository.delete_user(canonical_username)
