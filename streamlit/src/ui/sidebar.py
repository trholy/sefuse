"""Shared sidebar UI components for SeFuSe Streamlit pages.

This module is the canonical import point for sidebar helpers.
The implementation lives in ``auth.handlers`` to avoid a circular import
(``auth.handlers`` cannot import from ``ui.sidebar`` because ``ui.sidebar``
already imports from ``auth.handlers``).
"""

# Re-export for convenience so page modules can use:
#   from ui.sidebar import render_logout_button
from auth.handlers import render_logout_button  # noqa: F401
