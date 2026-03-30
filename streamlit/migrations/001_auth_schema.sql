CREATE TABLE IF NOT EXISTS auth_roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(32) UNIQUE NOT NULL
);

INSERT INTO auth_roles (name)
VALUES ('admin'), ('user')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS auth_users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES auth_roles(id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_auth_users_username
ON auth_users (username);

