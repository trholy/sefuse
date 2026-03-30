from functools import lru_cache

import streamlit as st

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
    return _get_settings().enabled


def bootstrap_auth_system() -> None:
    initialize_session_state()
    if not is_auth_enabled():
        return
    if get_bootstrap_flag():
        return

    auth_service = _get_authentication_service()
    auth_service.bootstrap_admin_user()
    set_bootstrap_flag(True)


def login_user(username: str, password: str) -> bool:
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
    clear_authenticated_user()


def is_authenticated() -> bool:
    if not is_auth_enabled():
        return True
    return session_is_authenticated()


def is_admin() -> bool:
    if not is_auth_enabled():
        return True
    return session_is_admin()


def require_login() -> None:
    if not is_auth_enabled():
        return
    if is_authenticated():
        return
    st.title("Authentication Required")
    st.info("Please log in on the Home page to access this page.")
    st.stop()


def require_admin() -> None:
    if not is_auth_enabled():
        return
    require_login()
    if is_admin():
        return
    st.error("Admin access required.")
    st.stop()


def render_logout_button() -> None:
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
    auth_service = _get_authentication_service()
    auth_service.create_user(username=username, password=password, role=role)


def update_password(username: str, new_password: str) -> None:
    user_service = _get_user_management_service()
    user_service.update_password(username=username, new_password=new_password)


def delete_user(username: str) -> None:
    user_service = _get_user_management_service()
    user_service.delete_user(username=username)


def to_user_message(error: Exception) -> str:
    if isinstance(error, AuthenticationError):
        return "Invalid username or password."
    if isinstance(error, UserAlreadyExistsError):
        return str(error)
    if isinstance(error, UserNotFoundError):
        return str(error)
    if isinstance(error, (ValidationError, AuthorizationError, ConfigurationError)):
        return str(error)
    return "An unexpected authentication error occurred."
