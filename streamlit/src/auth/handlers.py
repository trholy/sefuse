import logging
from functools import lru_cache

import streamlit as st
from psycopg2 import OperationalError

from .config import AuthSettings, load_auth_settings
from .constants import ROLE_USER, SESSION_DB_TOKEN, SESSION_ROLE, SESSION_USERNAME
from .cookies import clear_session_cookie, read_session_cookie, set_session_cookie
from .db import Database
from .exceptions import (
    AccountDeactivatedError,
    AccountLockedError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    UserAlreadyExistsError,
    UserNotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)
from .notification_repository import NotificationRepository
from .repository import PostgresUserRepository
from .saved_search_repository import SavedSearchRepository
from .security import PasswordHasher
from .services import AuthenticationService, UserManagementService
from .session_repository import SessionRepository
from .watchlist_repository import WatchlistRepository
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
def get_settings() -> AuthSettings:
    """Return the cached `AuthSettings` instance loaded from environment variables."""
    return load_auth_settings()


@lru_cache(maxsize=1)
def _get_authentication_service() -> AuthenticationService:
    """Return the cached `AuthenticationService` wired to the current settings."""
    settings = get_settings()
    database = Database(settings)
    repository = PostgresUserRepository(database)
    password_hasher = PasswordHasher(rounds=settings.bcrypt_rounds)
    return AuthenticationService(repository, password_hasher, settings)


@lru_cache(maxsize=1)
def _get_user_management_service() -> UserManagementService:
    """Return the cached `UserManagementService` wired to the current settings."""
    settings = get_settings()
    database = Database(settings)
    repository = PostgresUserRepository(database)
    password_hasher = PasswordHasher(rounds=settings.bcrypt_rounds)
    return UserManagementService(repository, password_hasher, settings)


@lru_cache(maxsize=1)
def _get_session_repository() -> SessionRepository:
    """Return the cached `SessionRepository` wired to the current settings."""
    settings = get_settings()
    database = Database(settings)
    return SessionRepository(database)


@lru_cache(maxsize=1)
def get_watchlist_repository() -> WatchlistRepository:
    """Return the cached `WatchlistRepository` wired to the current settings."""
    return WatchlistRepository(Database(get_settings()))


@lru_cache(maxsize=1)
def get_saved_search_repository() -> SavedSearchRepository:
    """Return the cached `SavedSearchRepository` wired to the current settings."""
    return SavedSearchRepository(Database(get_settings()))


@lru_cache(maxsize=1)
def get_notification_repository() -> NotificationRepository:
    """Return the cached `NotificationRepository` wired to the current settings."""
    return NotificationRepository(Database(get_settings()))


@lru_cache(maxsize=1)
def get_user_repository() -> PostgresUserRepository:
    """Return the cached `PostgresUserRepository` wired to the current settings."""
    return PostgresUserRepository(Database(get_settings()))


def alerts_enabled() -> bool:
    """Return True if saved-search alerts are switched on for this deployment.

    The master switch (`ALERTS_ENABLED`). When off, every alert surface is
    hidden: the Notification Settings page, the alert inbox and settings on the
    Saved Searches page, the alert controls in the save-search dialog, and the
    sidebar unread badge. Saved searches themselves keep working.
    """
    from shared.alerts_config import alerts_enabled as _alerts_enabled

    return _alerts_enabled()


def gotify_push_enabled() -> bool:
    """Return True if Gotify push is switched on and correctly configured.

    Thin wrapper over `shared.gotify_config.push_enabled`, which FastAPI's alert
    service uses too — the rule for "is push usable" has to be the same on both
    sides or the two services disagree about whether a user can be reached. Kept
    under this name because `ui.navigation` and the Notification Settings page
    both gate on it, and auth.handlers is where Streamlit's page-level gates live.
    """
    from shared.gotify_config import push_enabled

    return push_enabled()


def get_user_gotify_token(user_id: int) -> str:
    """Return the user's decrypted Gotify token, or `""` when unavailable.

    Swallows database and decryption errors the way
    `get_unread_notification_count` does — callers use this to decide what to
    render, never to gate access.
    """
    try:
        return get_user_repository().get_gotify_token(user_id)
    except Exception:
        logger.warning("Could not read Gotify token", exc_info=True)
        return ""


def is_auth_enabled() -> bool:
    """Return True if authentication is enabled via the `AUTH_ENABLED` env var."""
    return get_settings().enabled


def are_session_cookies_enabled() -> bool:
    """Return True if cross-tab session cookies are active."""
    return get_settings().session_cookies_enabled


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

    if not session_is_authenticated() and get_settings().session_cookies_enabled:
        _try_restore_session_from_cookie()


def _try_restore_session_from_cookie() -> None:
    """Check for a session cookie and restore session state from DB if valid."""
    token = read_session_cookie()
    if not token:
        return

    try:
        session_repo = _get_session_repository()
        settings = get_settings()
        user_info = session_repo.validate_and_refresh(
            token, settings.session_timeout_minutes
        )
    except Exception:
        return

    if user_info is None:
        clear_session_cookie(secure=settings.session_cookie_secure)
        return

    from datetime import datetime

    from .models import UserRecord

    user = UserRecord(
        id=user_info["user_id"],
        username=user_info["username"],
        password_hash="",
        role=user_info["role"],
        is_active=True,
        created_at=datetime.min,
        updated_at=datetime.min,
    )
    set_authenticated_user(user, db_token=token)


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
    except ConfigurationError as error:
        st.error(
            f"**Configuration error:** {error}\n\n"
            "**To fix this:**\n"
            "1. Copy `.env.example` to `.env`\n"
            "2. Replace all `change_me_*` values with real secrets\n"
            "3. Restart with `docker-compose up --build`\n\n"
            "See **README.md → Security Notes** for details."
        )
        st.stop()
    except Exception:
        logger.exception("Auth initialization failed")
        st.error("Authentication initialization failed. Please contact the administrator.")
        st.stop()


def login_user(username: str, password: str) -> bool:
    """Authenticate a user and write them into session state on success.

    On successful login the browser cookie is set via JavaScript which
    also triggers a page reload.  The caller should **not** call
    ``st.rerun()`` afterwards — the JS-initiated reload ensures the
    cookie is written before the page refreshes so that new tabs can
    restore the session.

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
    except (AccountDeactivatedError, AccountLockedError):
        raise
    except AuthenticationError:
        return False

    settings = get_settings()
    if settings.session_cookies_enabled:
        session_repo = _get_session_repository()
        token = session_repo.create_session(user.id, settings.session_timeout_minutes)
        set_authenticated_user(user, db_token=token)
        set_session_cookie(
            token,
            settings.session_timeout_minutes * 60,
            reload=True,
            secure=settings.session_cookie_secure,
        )
        st.stop()
    else:
        set_authenticated_user(user)
        st.rerun()
    return True


def logout_user() -> None:
    """Clear authenticated user from session state, DB session, and cookie.

    Clears the browser cookie via JavaScript which also triggers a page
    reload.  The caller should **not** call ``st.rerun()`` afterwards.
    """
    settings = get_settings()
    token = st.session_state.get(SESSION_DB_TOKEN)
    if token:
        try:
            session_repo = _get_session_repository()
            session_repo.delete_session(token)
        except Exception:
            pass
    clear_authenticated_user()
    if settings.session_cookies_enabled:
        clear_session_cookie(reload=True, secure=settings.session_cookie_secure)
        st.stop()
    else:
        st.rerun()


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


def require_page_access(page_title: str, disabled_note: str) -> int:
    """Run the whole entry gate for a logged-in-only page and return the user id.

    Every page that needs a `user_id` opened with the same six steps: bootstrap,
    explain itself and stop when auth is switched off for the deployment, require a
    login, render the sidebar logout button, then read the id out of the session and
    stop if it is missing. That last part had no helper at all, so it was written out
    in full on each page.

    Deliberately does **not** render the page title on the success path. The three
    callers place their own `st.title` at different points — the Saved Searches page
    renders its alert-matches section above the title — so titling here would reorder
    a page rather than tidy it. The title is rendered only on the auth-disabled
    branch, which is the one place all three agreed.

    Args:
        page_title (str): Heading shown *only* when authentication is disabled, so
            the page still identifies itself while explaining why it is empty.
        disabled_note (str): Sentence completing "Authentication is disabled. …".
            Passed in rather than derived from `page_title` because the subject's
            number varies ("Watchlist requires", "Saved searches require").

    Returns:
        int: The authenticated user's id.

    Note:
        Returns only when access is granted. Every other path ends in `st.stop()`,
        which raises, so callers can treat the result as always present.
    """
    from .constants import SESSION_USER_ID

    safe_bootstrap()

    if not is_auth_enabled():
        st.title(page_title)
        st.info(f"Authentication is disabled. {disabled_note}")
        st.stop()

    require_login()
    render_logout_button()

    user_id = st.session_state.get(SESSION_USER_ID)
    if user_id is None:
        st.warning("User session not found. Please log in again.")
        st.stop()
    return user_id


def get_unread_notification_count() -> int:
    """Return the number of unread alert notifications for the current user.

    Returns 0 if alerts are switched off for the deployment, auth is disabled,
    the user is not authenticated, or the database is unreachable. The alerts
    check is what removes the sidebar badge in `render_logout_button`.
    """
    if not alerts_enabled():
        return 0
    if not is_auth_enabled() or not is_authenticated():
        return 0
    from .constants import SESSION_USER_ID

    user_id = st.session_state.get(SESSION_USER_ID)
    if user_id is None:
        return 0
    try:
        repo = get_notification_repository()
        return repo.get_unread_count(user_id)
    except Exception:
        return 0


def render_logout_button() -> None:
    """Render a sidebar logout button, notification badge, and username caption.

    Note: this is a UI concern and is re-exported via ``ui.sidebar`` for
    callers that prefer that module.  It lives here to avoid a circular
    import (``ui.sidebar`` imports from this module).
    """
    if not is_auth_enabled():
        return
    if not is_authenticated():
        return

    role = st.session_state.get(SESSION_ROLE, ROLE_USER)
    username = st.session_state.get(SESSION_USERNAME, "")
    st.sidebar.caption(f"Logged in as `{username}` ({role})")

    unread = get_unread_notification_count()
    if unread > 0:
        st.sidebar.markdown(f"**Alerts ({unread} new)**")

    if st.sidebar.button("Logout", key="logout_button"):
        logout_user()


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


def set_user_active(username: str, active: bool) -> None:
    """Activate or deactivate a non-admin user account.

    Args:
        username (str): Username of the account to update.
        active (bool): True to activate, False to deactivate.
    """
    user_service = _get_user_management_service()
    user_service.set_user_active(username=username, active=active)


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
    if isinstance(
        error,
        (
            AccountDeactivatedError,
            AccountLockedError,
            UserAlreadyExistsError,
            UserNotFoundError,
            ValidationError,
            AuthorizationError,
            ConfigurationError,
        ),
    ):
        return str(error)
    return "An unexpected authentication error occurred."
