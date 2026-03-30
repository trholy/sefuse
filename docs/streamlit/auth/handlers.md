# `streamlit.auth.handlers` 
 
Provides the Streamlit-facing authentication handlers used by page modules. 
 
## Responsibilities 
 
- Lazily loads authentication settings and constructs service instances. 
- Bootstraps the admin account once per Streamlit session. 
- Exposes login, logout, and session-based access checks. 
- Provides `require_login()` and `require_admin()` guards for page entry points. 
- Renders the sidebar logout control for authenticated users. 
- Bridges user management actions from the admin page to the service layer. 
- Converts service and validation exceptions into short user-facing messages.
