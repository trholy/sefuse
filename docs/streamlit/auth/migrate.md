# `streamlit.auth.migrate`

Applies SQL-based authentication schema migrations to the PostgreSQL database.

---

### `apply_migrations() -> None`

Apply all pending SQL migration files to the auth database.

Discovers `.sql` files in the `migrations/` directory located adjacent to this module, creates the `schema_migrations` tracking table if it does not exist, and runs each unapplied file exactly once in alphabetical (version) order.

No-op when `AUTH_ENABLED=false`.

**Returns:** `None`

**Raises:**

- `RuntimeError` — if no `.sql` migration files are found in the migrations directory.
- `psycopg2.OperationalError` — if the database connection cannot be established.

---

## Module-level execution

When run as a script (`python -m auth.migrate`), calls `apply_migrations()` directly. This is invoked in the Streamlit container's `CMD` before starting the Streamlit server.
