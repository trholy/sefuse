import streamlit as st

from auth.constants import ROLE_ADMIN
from auth.handlers import (
    safe_bootstrap,
    create_user,
    delete_user,
    is_auth_enabled,
    list_users,
    render_logout_button,
    require_admin,
    to_user_message,
    update_password,
)

st.set_page_config(
    page_title="SeFuSe - Admin User Management",
    layout="centered",
    page_icon="favicon.jpg",
)


def _render_create_user() -> None:
    """Render the Create User form and create a new account on submit.

    Displays username and password fields. On successful submission calls
    ``create_user`` and triggers a page rerun; on failure shows an error message
    via ``st.error``.
    """
    st.subheader("Create User")
    with st.form("create_user_form", clear_on_submit=True):
        username = st.text_input("Username", key="create_username")
        password = st.text_input("Password", type="password", key="create_password")
        submitted = st.form_submit_button("Create user")

    if not submitted:
        return

    try:
        create_user(username=username, password=password)
    except Exception as error:
        st.error(to_user_message(error))
        return

    st.success(f"User `{username}` created.")
    st.rerun()


def _render_update_password(usernames: list[str]) -> None:
    """Render the Update Password form and apply the change on submit.

    Args:
        usernames (list[str]): All current usernames, shown in a selectbox so the
            admin can choose whose password to change.

    Displays a selectbox and new-password field. On successful submission calls
    ``update_password`` and triggers a page rerun; on failure shows an error message
    via ``st.error``.
    """
    st.subheader("Update Password")
    with st.form("update_password_form", clear_on_submit=True):
        username = st.selectbox("Username", usernames, key="update_username")
        new_password = st.text_input(
            "New password",
            type="password",
            key="update_password_value",
        )
        submitted = st.form_submit_button("Update password")

    if not submitted:
        return

    try:
        update_password(username=username, new_password=new_password)
    except Exception as error:
        st.error(to_user_message(error))
        return

    st.success(f"Password updated for `{username}`.")
    st.rerun()


def _render_delete_user(deletable_usernames: list[str]) -> None:
    """Render the Delete User form and permanently remove an account on confirmed submit.

    Args:
        deletable_usernames (list[str]): Non-admin usernames eligible for deletion.
            When empty, renders an informational message and returns immediately.

    Displays a selectbox, a confirmation checkbox, and a submit button. Requires the
    confirmation checkbox to be ticked before deletion proceeds. On successful
    submission calls ``delete_user`` and triggers a page rerun; on failure shows an
    error message via ``st.error``.
    """
    st.subheader("Delete User")
    if not deletable_usernames:
        st.info("No non-admin users available for deletion.")
        return

    with st.form("delete_user_form"):
        username = st.selectbox("Username", deletable_usernames, key="delete_username")
        confirmed = st.checkbox("I understand this action cannot be undone.")
        submitted = st.form_submit_button("Delete user")

    if not submitted:
        return

    if not confirmed:
        st.error("Please confirm deletion first.")
        return

    try:
        delete_user(username=username)
    except Exception as error:
        st.error(to_user_message(error))
        return

    st.success(f"User `{username}` deleted.")
    st.rerun()


safe_bootstrap()

if not is_auth_enabled():
    st.title("Admin User Management")
    st.info(
        "Authentication is disabled (`AUTH_ENABLED=false`)."
        " User management is not active."
    )
    st.stop()

require_admin()
render_logout_button()

st.title("Admin User Management")
users = list_users()

if users:
    st.table(users)
else:
    st.info("No users found.")

all_usernames = [user["username"] for user in users]
deletable_usernames = [
    user["username"]
    for user in users
    if user.get("role") != ROLE_ADMIN
]

_render_create_user()
if all_usernames:
    _render_update_password(all_usernames)
_render_delete_user(deletable_usernames)
