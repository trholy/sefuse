import os
from typing import Any

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_USER}

SESSION_AUTHENTICATED = "auth_authenticated"
SESSION_USERNAME = "auth_username"
SESSION_ROLE = "auth_role"
SESSION_DB_READY = "auth_db_ready"


def is_auth_enabled() -> bool:
    value = (os.getenv("AUTH_ENABLED") or "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _db_settings() -> dict[str, Any]:
    return {
        "host": os.getenv("DB_HOST", "postgres"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "sefuse"),
        "user": os.getenv("DB_USER", "sefuse"),
        "password": os.getenv("DB_PASSWORD", "sefuse"),
        "connect_timeout": 5,
    }


def _connect():
    return psycopg2.connect(**_db_settings())


def _normalize_username(username: str) -> str:
    normalized = (username or "").strip()
    if not normalized:
        raise ValueError("Username is required.")
    if len(normalized) < 3:
        raise ValueError("Username must contain at least 3 characters.")
    if any(character.isspace() for character in normalized):
        raise ValueError("Username must not contain whitespace.")
    return normalized


def _validate_password(password: str) -> None:
    if not password:
        raise ValueError("Password is required.")
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def init_auth_state() -> None:
    st.session_state.setdefault(SESSION_AUTHENTICATED, False)
    st.session_state.setdefault(SESSION_USERNAME, None)
    st.session_state.setdefault(SESSION_ROLE, None)
    st.session_state.setdefault(SESSION_DB_READY, False)


def _initialize_auth_storage() -> None:
    admin_username = (os.getenv("ADMIN_USERNAME") or "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD") or ""
    if not admin_username or not admin_password:
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD must be set.")

    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(150) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'user'))
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO app_users (username, password_hash, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (username)
                DO UPDATE SET password_hash = EXCLUDED.password_hash, role = EXCLUDED.role
                """,
                (admin_username, _hash_password(admin_password), ROLE_ADMIN),
            )
        connection.commit()


def bootstrap_auth_system() -> None:
    init_auth_state()
    if not is_auth_enabled():
        return
    if st.session_state[SESSION_DB_READY]:
        return
    _initialize_auth_storage()
    st.session_state[SESSION_DB_READY] = True


def _get_user(username: str) -> dict[str, Any] | None:
    with _connect() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT id, username, password_hash, role FROM app_users WHERE username = %s",
                (username,),
            )
            row = cursor.fetchone()
    return dict(row) if row else None


def login_user(username: str, password: str) -> bool:
    if not password:
        return False

    try:
        normalized_username = _normalize_username(username)
    except ValueError:
        return False

    user = _get_user(normalized_username)
    if not user:
        return False

    if not _verify_password(password, user["password_hash"]):
        return False

    st.session_state[SESSION_AUTHENTICATED] = True
    st.session_state[SESSION_USERNAME] = user["username"]
    st.session_state[SESSION_ROLE] = user["role"]
    return True


def logout_user() -> None:
    st.session_state[SESSION_AUTHENTICATED] = False
    st.session_state[SESSION_USERNAME] = None
    st.session_state[SESSION_ROLE] = None


def is_authenticated() -> bool:
    return bool(st.session_state.get(SESSION_AUTHENTICATED, False))


def is_admin() -> bool:
    return st.session_state.get(SESSION_ROLE) == ROLE_ADMIN


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

    role = st.session_state.get(SESSION_ROLE, ROLE_USER)
    username = st.session_state.get(SESSION_USERNAME, "")
    st.sidebar.caption(f"Logged in as `{username}` ({role})")

    if st.sidebar.button("Logout", key="logout_button"):
        logout_user()
        st.rerun()


def list_users() -> list[dict[str, Any]]:
    with _connect() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT id, username, role FROM app_users ORDER BY username ASC"
            )
            rows = cursor.fetchall()
    return [dict(row) for row in rows]


def create_user(username: str, password: str, role: str = ROLE_USER) -> None:
    normalized_username = _normalize_username(username)
    _validate_password(password)
    if role not in ALLOWED_ROLES:
        raise ValueError("Invalid role.")

    if _get_user(normalized_username):
        raise ValueError("Username already exists.")

    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES (%s, %s, %s)",
                (normalized_username, _hash_password(password), role),
            )
        connection.commit()


def update_password(username: str, new_password: str) -> None:
    normalized_username = _normalize_username(username)
    _validate_password(new_password)

    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE app_users SET password_hash = %s WHERE username = %s",
                (_hash_password(new_password), normalized_username),
            )
            if cursor.rowcount == 0:
                raise ValueError("User does not exist.")
        connection.commit()


def delete_user(username: str) -> None:
    normalized_username = _normalize_username(username)

    with _connect() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT role FROM app_users WHERE username = %s",
                (normalized_username,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("User does not exist.")
            if row["role"] == ROLE_ADMIN:
                raise ValueError("Admin users cannot be deleted.")

            cursor.execute(
                "DELETE FROM app_users WHERE username = %s",
                (normalized_username,),
            )
        connection.commit()
