# `streamlit.pages.3_Admin_User_Management` 
 
Entry-point module for the admin-only user management page in Streamlit. 
 
## Behavior 
 
- Configures the admin page and initializes the authentication system. 
- Stops early with an informational message when authentication is globally disabled. 
- Requires an authenticated admin session before rendering user management controls. 
- Lists existing users with role and activity metadata. 
- Provides forms to create users, update passwords, and delete non-admin users. 
- Maps service-layer authentication and validation errors to user-facing Streamlit messages.
