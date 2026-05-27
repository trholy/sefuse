# `streamlit.pages.2_EU_Funding_Programs`

Entry-point script for the EU funding search page.

This module contains no function or class definitions. It executes the following steps at import time:

| Step | Action |
|---|---|
| 1 | `safe_bootstrap()` — initialises session state and the admin user; stops on failure. |
| 2 | `require_login()` — redirects unauthenticated users to the home page. |
| 3 | Instantiates `EuFundingSearchPage()` and calls `.render()`. |
| 4 | `render_logout_button()` — renders the sidebar logout control. |
