"""Gotify push-notification client, shared by FastAPI and Streamlit.

FastAPI uses it from the nightly alert job; Streamlit uses it to verify a user's
token and to send test notifications. Both talk to the one central server named
by ``GOTIFY_URL`` (see :mod:`shared.gotify_config`).

Uses ``requests`` because it is the only HTTP client already pinned in *both*
services' requirements. Every call is given an explicit timeout — an
unresponsive Gotify server must never stall the nightly cron.

No function here raises on a delivery failure: sends return ``False`` and log,
so one broken notification target cannot abort an alert run.
"""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse, urlunparse

import requests

from .gotify_config import GotifyConfigError, get_gotify_config

logger = logging.getLogger(__name__)

_HTTP_SCHEMES = {"http", "https"}
# Names that, from inside a container, mean this Docker stack's own services or
# the container itself — never a Gotify server, so most likely a typo.
_BLOCKED_HOSTNAMES = {
    "localhost", "qdrant", "postgres", "ollama", "fastapi", "streamlit",
}

# Gotify renders markdown only when the message declares this content type;
# without it clients show the raw `[title](url)` text instead of a link.
_MARKDOWN_EXTRAS = {"client::display": {"contentType": "text/markdown"}}


def is_allowed_gotify_url(url: str) -> bool:
    """Return True if ``url`` is a usable Gotify server address.

    This is a sanity check on the *operator-supplied* ``GOTIFY_URL``, not a
    defence against a hostile submitter: users never enter a URL. It requires
    an http(s) URL with a host, and rejects only addresses that cannot be a
    Gotify server from inside a container — the stack's own service names and
    the container's loopback.

    Private and LAN addresses are allowed, because a self-hosted Gotify
    usually sits on the same network as SeFuSe. Hostnames are not resolved:
    whether the server answers is :func:`verify_server`'s job.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    scheme = (parsed.scheme or "").lower()
    if scheme not in _HTTP_SCHEMES:
        return False
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False

    if hostname in _BLOCKED_HOSTNAMES:
        return False

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return not (addr.is_loopback or addr.is_unspecified)


def normalize_server_url(server_url: str) -> str:
    """Reduce a configured server address to a bare scheme://host[:port] base.

    Any path, query, or fragment is dropped; callers append the endpoint. The
    configured scheme is preserved and defaults to ``https`` when absent, so a
    bare ``gotify.example.com`` is treated as HTTPS rather than silently
    downgraded.

    Args:
        server_url (str): Raw value, e.g. ``"gotify.example.com"`` or
            ``"https://gotify.example.com/some/path"``.

    Returns:
        str: Normalised base, e.g. ``"https://gotify.example.com"``. Returns
        ``""`` for empty input.
    """
    raw = (server_url or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    if not parsed.scheme:
        # No scheme: urlparse puts the whole thing in .path, not .netloc.
        netloc = parsed.path.split("/", 1)[0]
        scheme = "https"
    else:
        netloc = parsed.netloc or parsed.path.split("/", 1)[0]
        scheme = parsed.scheme.lower()

    return urlunparse((scheme, netloc, "", "", "", "")).rstrip("/")


def _endpoint(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def verify_server(base_url: str, timeout: float | None = None) -> tuple[bool, str]:
    """Check that ``base_url`` really is a Gotify server.

    Calls the unauthenticated ``GET /version`` endpoint, which every Gotify
    server exposes and which returns JSON carrying a ``version`` key. A host
    that answers 200 with something else is reported as "not a Gotify server"
    rather than accepted.

    Args:
        base_url (str): Normalised base URL.
        timeout (float | None): Override the configured HTTP timeout.

    Returns:
        tuple[bool, str]: ``(ok, reason)``. ``reason`` is human-readable and
        safe to show in the UI or write to a log.
    """
    if not base_url:
        return False, "No Gotify server URL configured."
    timeout = timeout if timeout is not None else _default_timeout()

    try:
        response = requests.get(_endpoint(base_url, "version"), timeout=timeout)
    except requests.RequestException as exc:
        return False, f"Could not reach {base_url}: {exc}"

    if not response.ok:
        return False, (
            f"{base_url} answered HTTP {response.status_code} for /version."
        )
    try:
        payload = response.json()
    except ValueError:
        return False, f"{base_url} did not return JSON — not a Gotify server."
    if not isinstance(payload, dict) or "version" not in payload:
        return False, f"{base_url} does not look like a Gotify server."
    return True, f"Gotify {payload.get('version')} at {base_url}."


def verify_token(
    base_url: str, token: str, timeout: float | None = None
) -> tuple[bool, str]:
    """Check that ``token`` is a valid application token on ``base_url``.

    Gotify application tokens may only *write* messages, so the read-oriented
    ``/current/user`` endpoint rejects them. The reliable check is therefore a
    ``POST /message`` — this sends a real notification, which is why the caller
    should present it to the user as "verify and send a test notification"
    rather than a silent validation.

    Returns:
        tuple[bool, str]: ``(ok, reason)`` — ``reason`` is UI-safe.
    """
    if not token:
        return False, "No app token provided."
    ok = GotifyClient(token, base=base_url, timeout=timeout).send(
        "SeFuSe", "Notifications are set up correctly."
    )
    if ok:
        return True, "Token accepted — a test notification has been sent."
    return False, (
        "Gotify rejected this token. Check that you copied an *application* "
        "token from the correct server."
    )


def _default_timeout() -> float:
    """Configured timeout, falling back to the default when unconfigured."""
    try:
        return get_gotify_config().timeout
    except GotifyConfigError:
        from .gotify_config import DEFAULT_TIMEOUT_SECONDS

        return DEFAULT_TIMEOUT_SECONDS


class GotifyClient:
    """Sends messages to one user's channel on the central Gotify server.

    Args:
        token (str): The user's Gotify *application* token. Empty tokens are
            tolerated and turn every send into a logged no-op, so callers need
            not special-case unconfigured users.
        base (str | None): Server base URL. Defaults to the configured
            ``GOTIFY_URL``.
        priority (int | None): Message priority. Defaults to ``GOTIFY_PRIORITY``.
        timeout (float | None): HTTP timeout. Defaults to
            ``GOTIFY_TIMEOUT_SECONDS``.
    """

    def __init__(
        self,
        token: str,
        *,
        base: str | None = None,
        priority: int | None = None,
        timeout: float | None = None,
    ):
        try:
            config = get_gotify_config()
        except GotifyConfigError:
            config = None

        self.token = (token or "").strip()
        self.base = (base if base is not None else getattr(config, "base_url", ""))
        self.priority = (
            priority
            if priority is not None
            else getattr(config, "priority", None)
        )
        if self.priority is None:
            from .gotify_config import DEFAULT_PRIORITY

            self.priority = DEFAULT_PRIORITY
        self.timeout = (
            timeout if timeout is not None else _default_timeout()
        )

    def send(self, title: str, message: str, *, markdown: bool = True) -> bool:
        """Push one message. Returns True only when Gotify accepted it.

        Never raises: transport errors and rejections are logged and reported
        as ``False`` so a failed notification cannot abort an alert run.

        Args:
            title (str): Notification title.
            message (str): Body. May contain markdown when ``markdown`` is set.
            markdown (bool): Ask clients to render the body as markdown, which
                is what turns an embedded ``[name](url)`` into a tappable link.

        Returns:
            bool: True on a 2xx response.
        """
        if not self.token:
            logger.warning("Gotify send skipped: no app token configured")
            return False
        if not self.base:
            logger.warning("Gotify send skipped: no server URL configured")
            return False
        if not is_allowed_gotify_url(self.base):
            logger.warning(
                "Gotify send skipped: server URL is not a usable http(s) address"
            )
            return False

        payload = {
            "title": title,
            "message": message,
            "priority": self.priority,
        }
        if markdown:
            payload["extras"] = _MARKDOWN_EXTRAS

        try:
            response = requests.post(
                _endpoint(self.base, "message"),
                json=payload,
                headers={"X-Gotify-Key": self.token},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.error("Gotify request failed: %s", exc)
            return False

        if not response.ok:
            # Never log the token, and never log a response body that might
            # echo it back.
            logger.error(
                "Gotify rejected the message: HTTP %s", response.status_code
            )
            return False
        return True
