from pathlib import Path

import psycopg2

from .config import load_auth_settings


def _migrations_dir() -> Path:
    current_path = Path(__file__).resolve()
    candidates = [
        current_path.parents[1] / "migrations",
        current_path.parents[2] / "migrations",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _sorted_migrations() -> list[Path]:
    return sorted(_migrations_dir().glob("*.sql"))


def apply_migrations() -> None:
    settings = load_auth_settings()
    if not settings.enabled:
        return
    migration_files = _sorted_migrations()
    if not migration_files:
        raise RuntimeError("No SQL migration files found.")

    with psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        connect_timeout=settings.db_connect_timeout_seconds,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}

            for migration_path in migration_files:
                version = migration_path.stem
                if version in applied:
                    continue

                sql_text = migration_path.read_text(encoding="utf-8")
                cursor.execute(sql_text)
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
        connection.commit()


if __name__ == "__main__":
    apply_migrations()
