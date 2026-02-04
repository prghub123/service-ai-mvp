"""Alembic migration environment configuration."""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Import our app configuration and models
from app.config import get_settings
from app.database import Base

# Import all models so Alembic can detect them for autogenerate
from app.models import (
    Business,
    Customer,
    CustomerAddress,
    OTPCode,
    Technician,
    TechnicianSkill,
    Job,
    JobNote,
    JobPhoto,
    JobStatusHistory,
    ScheduleBlock,
    SlotReservation,
    Notification,
    NotificationStatus,
)
# Also import CallLog from notification module
from app.models.notification import CallLog

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from our app settings
settings = get_settings()

# Convert async URL to sync for Alembic (replace asyncpg with psycopg2)
# Alembic migrations run synchronously
database_url = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
config.set_main_option("sqlalchemy.url", database_url)

# Set target metadata from our Base - this enables autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
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
