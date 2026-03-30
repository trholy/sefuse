# `streamlit.auth.services` 
 
Defines the business-logic layer for authentication and user management. 
 
## Class `AuthenticationService` 
 
Handles credential and account lifecycle rules. 
 
### Key Behavior 
 
- Creates the configured admin user when it does not yet exist. 
- Refuses startup when `ADMIN_USERNAME` already exists with a non-admin role. 
- Normalizes usernames and validates password strength before persistence. 
- Verifies login credentials through the repository and password hasher. 
- Rejects inactive users and invalid credentials with a generic authentication error. 
- Creates regular users for admin-managed user provisioning. 
 
## Class `UserManagementService` 
 
Handles administrative user maintenance. 
 
### Key Behavior 
 
- Returns user summaries for the admin UI. 
- Updates password hashes after password validation. 
- Prevents deletion of admin users. 
- Delegates persistence operations to the repository layer.
