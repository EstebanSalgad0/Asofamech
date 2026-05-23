import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# Mirror the encoding fix in db.py — psycopg2 on Windows can read system paths
# that contain Latin-1 characters (e.g. "Escritorio"), causing UnicodeDecodeError.
os.environ["PGCLIENTENCODING"] = "UTF8"

# Import Base and all ORM models so they are registered in Base.metadata.
# This is required for --autogenerate to detect the current schema.
from app.db import Base  # noqa: F401
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Read DATABASE_URL from environment (same source as the FastAPI app)."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://app_user:app_pass@localhost:5432/app_db",
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to the DB)."""
    # Use create_engine directly (matches db.py) to avoid engine_from_config
    # reading stale ini options that bypass the PGCLIENTENCODING fix.
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
        connect_args={"client_encoding": "utf8"},
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
