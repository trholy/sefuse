from functools import lru_cache

import streamlit as st
from psycopg2 import OperationalError

from .config import AuthSettings, load_auth_settings
from .constants import ROLE_USER
from .db import Database
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    UserAlreadyExistsError,
    UserNotFoundError,
    ValidationError,
)
from .repository import PostgresUserRepository
from .security import PasswordHasher
from .services import AuthenticationService, UserManagementService
from .session import (
    clear_authenticated_user,
    get_bootstrap_flag,
    initialize_session_state,
    is_admin as session_is_admin,
    is_authenticated as session_is_authenticated,
    set_authenticated_user,
    set_bootstrap_flag,
)


@lru_cache(maxsize=1)
def _get_settings() -> AuthSettings:
    return load_auth_settings()


@lru_cache(maxsize=1)
def _get_authentication_service() -> AuthenticationService:
    settings = _get_settings()
    database = Database(settings)
    repository = PostgresUserRepository(database)
    password_hasher = PasswordHasher(rounds=settings.bcrypt_rounds)
    return AuthenticationService(repository, password_hasher, settings)


@lru_cache(maxsize=1)
def _get_user_management_service() -> UserManagementService:
    settings = _get_settings()
    database = Database(settings)
    repository = PostgresUserRepository(database)
    password_hasher = PasswordHasher(rounds=settings.bcrypt_rounds)
    return UserManagementService(repository, password_hasher, settings)


def is_auth_enabled() -> bool:
    """Return True if authentication is enabled via the `AUTH_ENABLED` env var."""
    return _get_settings().enabled


def bootstrap_auth_system() -> None:
    """Initialise session state and create the admin user on first call per session.

    No-op when auth is disabled or the bootstrap flag is already set.
    """
    initialize_session_state()
    if not is_auth_enabled():
        return
    if get_bootstrap_flag():
        return

    auth_service = _get_authentication_service()
    auth_service.bootstrap_admin_user()
    set_bootstrap_flag(True)


def safe_bootstrap() -> None:
    """Bootstrap auth and stop the page with a user-facing error on failure."""
    try:
        bootstrap_auth_system()
    except OperationalError:
        st.error(
            "Could not connect to the authentication database."
            " Please check Docker Compose and DB credentials."
        )
        st.stop()
    except Exception as error:
        st.error(f"Authentication initialization failed: {error}")
        st.stop()


def login_user(username: str, password: str) -> bool:
    """Authenticate a user and write them into session state on success.

    Args:
        username (str): Raw username from the login form.
        password (str): Plain-text password attempt.

    Returns:
        bool: True on successful login, False on invalid credentials.
            Always returns True when auth is disabled.
    """
    if not is_auth_enabled():
        return True

    auth_service = _get_authentication_service()
    try:
        user = auth_service.authenticate(username, password)
    except AuthenticationError:
        return False
    set_authenticated_user(user)
    return True


def logout_user() -> None:
    """Clear authenticated user from session state (logout)."""
    clear_authenticated_user()


def is_authenticated() -> bool:
    """Return True if the current session has an authenticated user (or auth is disabled)."""
    if not is_auth_enabled():
        return True
    return session_is_authenticated()


def is_admin() -> bool:
    """Return True if the current session user has the admin role (or auth is disabled)."""
    if not is_auth_enabled():
        return True
    return session_is_admin()


def require_login() -> None:
    """Stop the Streamlit page with a login prompt if the user is not authenticated."""
    if not is_auth_enabled():
        return
    if is_authenticated():
        return
    st.title("Authentication Required")
    st.info("Please log in on the Home page to access this page.")
    st.stop()


def require_admin() -> None:
    """Stop the Streamlit page with an error if the user is not an admin."""
    if not is_auth_enabled():
        return
    require_login()
    if is_admin():
        return
    st.error("Admin access required.")
    st.stop()


def render_logout_button() -> None:
    """Render a sidebar logout button and username caption for authenticated users."""
    if not is_auth_enabled():
        return
    if not is_authenticated():
        return

    role = st.session_state.get("auth_role", ROLE_USER)
    username = st.session_state.get("auth_username", "")
    st.sidebar.caption(f"Logged in as `{username}` ({role})")
    if st.sidebar.button("Logout", key="logout_button"):
        logout_user()
        st.rerun()


def list_users() -> list[dict]:
    """Return all users as plain dicts for display in the admin page.

    Returns:
        list[dict]: Each dict contains id, username, role, is_active, created_at, updated_at.
    """
    user_service = _get_user_management_service()
    users = user_service.list_users()
    return [
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }
        for user in users
    ]


def create_user(username: str, password: str, role: str = ROLE_USER) -> None:
    """Create a new user via the authentication service.

    Args:
        username (str): Desired username.
        password (str): Plain-text password.
        role (str, default=ROLE_USER): Assigned role (`"user"` or `"admin"`).
    """
    auth_service = _get_authentication_service()
    auth_service.create_user(username=username, password=password, role=role)


def update_password(username: str, new_password: str) -> None:
    """Change a user's password via the user management service.

    Args:
        username (str): Username of the account to update.
        new_password (str): New plain-text password.
    """
    user_service = _get_user_management_service()
    user_service.update_password(username=username, new_password=new_password)


def delete_user(username: str) -> None:
    """Delete a non-admin user via the user management service.

    Args:
        username (str): Username of the account to delete.
    """
    user_service = _get_user_management_service()
    user_service.delete_user(username=username)


def to_user_message(error: Exception) -> str:
    """Convert a domain auth exception to a user-facing string.

    Args:
        error (Exception): Exception raised by an auth service method.

    Returns:
        str: Human-readable message suitable for `st.error(...)`.
    """
    if isinstance(error, AuthenticationError):
        return "Invalid username or password."
    if isinstance(error, UserAlreadyExistsError):
        return str(error)
    if isinstance(error, UserNotFoundError):
        return str(error)
    if isinstance(error, (ValidationError, AuthorizationError, ConfigurationError)):
        return str(error)
    return "An unexpected authentication error occurred."
