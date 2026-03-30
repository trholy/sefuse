# `streamlit.auth.migrate` 
 
Applies SQL-based authentication schema migrations for the Streamlit service. 
 
## Behavior 
 
- Loads database connection settings from the authentication configuration. 
- Skips migration execution when authentication is disabled. 
- Locates SQL files in the Streamlit `migrations` directory. 
- Maintains applied migration state in the `schema_migrations` table. 
- Executes unapplied SQL migration files in sorted order. 
- Raises an error when no migration files are available.
