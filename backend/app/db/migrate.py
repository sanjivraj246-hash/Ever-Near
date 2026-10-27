import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text, Table, Column, String, DateTime, MetaData, inspect
from app.db.session import engine as default_engine, Base
from app.models.entities import (
    User,
    ParentProfile,
    FamilyProfile,
    FamilyRelationship,
    TrustedContact,
    FamilyInvitation
)

logger = logging.getLogger("ever_near.migrate")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

INITIAL_ENTITIES = [
    User.__table__,
    ParentProfile.__table__,
    FamilyProfile.__table__,
    FamilyRelationship.__table__,
    TrustedContact.__table__,
    FamilyInvitation.__table__,
]

def init_migration_tracking(engine):
    """Ensures schema_migrations table exists for version tracking."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(128) PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL,
                description VARCHAR(256)
            );
        """))

def get_applied_migrations(engine):
    """Returns set of already applied migration versions."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version FROM schema_migrations"))
        return {row[0] for row in result.fetchall()}

def record_migration(engine, version: str, description: str):
    """Records an applied migration."""
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO schema_migrations (version, applied_at, description) VALUES (:v, :t, :d)"),
            {"v": version, "t": datetime.now(timezone.utc), "d": description}
        )

def ensure_initial_schema_columns(engine):
    """
    Ensures all 5 initial entities have created_at, updated_at and required columns
    even if created prior to Phase 5.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    is_postgres = "postgresql" in str(engine.url)

    columns_to_check = {
        "users": ["created_at", "updated_at"],
        "parent_profiles": ["created_at", "updated_at"],
        "family_profiles": ["created_at", "updated_at"],
        "family_relationships": ["created_at", "updated_at"],
        "trusted_contacts": ["created_at", "updated_at"]
    }

    with engine.begin() as conn:
        for table_name, cols in columns_to_check.items():
            if table_name in existing_tables:
                col_names = {c["name"] for c in inspector.get_columns(table_name)}
                for col_name in cols:
                    if col_name not in col_names:
                        logger.info(f"Adding missing column '{col_name}' to table '{table_name}'...")
                        if is_postgres:
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL"))
                        else:
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} TIMESTAMP"))
                            conn.execute(text(f"UPDATE {table_name} SET {col_name} = CURRENT_TIMESTAMP WHERE {col_name} IS NULL"))


def run_migrations(engine=None):
    """
    Executes database migrations and initialization for the 5 initial entities:
    - users
    - parent_profiles
    - family_profiles
    - family_relationships
    - trusted_contacts
    """
    if engine is None:
        engine = default_engine

    logger.info(f"Connecting to database engine: {engine.url.render_as_string(hide_password=True)}")
    init_migration_tracking(engine)
    applied = get_applied_migrations(engine)

    version_001 = "001_initial_schema"
    if version_001 not in applied:
        logger.info(f"Applying migration {version_001}: 5 Initial entities (users, parent_profiles, family_profiles, family_relationships, trusted_contacts)...")
        
        is_postgres = "postgresql" in str(engine.url)
        migrations_dir = Path(__file__).resolve().parent / "migrations"
        sql_file = migrations_dir / "001_initial_schema.sql"

        if is_postgres and sql_file.exists():
            logger.info("Executing native PostgreSQL DDL script...")
            with open(sql_file, "r", encoding="utf-8") as f:
                sql_content = f.read()
            with engine.begin() as conn:
                try:
                    # DBAPI raw connection natively supports multi-statement scripts with dollar-quoted blocks
                    raw_conn = getattr(conn, "connection", None)
                    if hasattr(raw_conn, "dbapi_connection"):
                        raw_cursor = raw_conn.dbapi_connection.cursor()
                    elif hasattr(raw_conn, "cursor"):
                        raw_cursor = raw_conn.cursor()
                    else:
                        raw_cursor = None

                    if raw_cursor:
                        raw_cursor.execute(sql_content)
                        raw_cursor.close()
                    else:
                        Base.metadata.create_all(bind=engine, tables=INITIAL_ENTITIES)
                except Exception as ex:
                    logger.warning(f"Native script notice ({ex}), ensuring tables via SQLAlchemy metadata...")
                    Base.metadata.create_all(bind=engine, tables=INITIAL_ENTITIES)
        else:
            logger.info("Creating initial entity tables via SQLAlchemy metadata (PostgreSQL/Relational engine)...")
            Base.metadata.create_all(bind=engine, tables=INITIAL_ENTITIES)

        record_migration(engine, version_001, "Initial 5 entities: users, parent_profiles, family_profiles, family_relationships, trusted_contacts")
        logger.info(f"Migration {version_001} applied successfully.")
    else:
        logger.info(f"Migration {version_001} is already recorded.")

    version_002 = "002_family_invitations"
    if version_002 not in applied:
        logger.info(f"Applying migration {version_002}: family_invitations...")
        is_postgres = "postgresql" in str(engine.url)
        migrations_dir = Path(__file__).resolve().parent / "migrations"
        sql_file = migrations_dir / "002_family_invitations.sql"

        if is_postgres and sql_file.exists():
            with open(sql_file, "r", encoding="utf-8") as f:
                sql_content = f.read()
            with engine.begin() as conn:
                try:
                    raw_conn = getattr(conn, "connection", None)
                    if hasattr(raw_conn, "dbapi_connection"):
                        raw_cursor = raw_conn.dbapi_connection.cursor()
                    elif hasattr(raw_conn, "cursor"):
                        raw_cursor = raw_conn.cursor()
                    else:
                        raw_cursor = None

                    if raw_cursor:
                        raw_cursor.execute(sql_content)
                        raw_cursor.close()
                    else:
                        Base.metadata.create_all(bind=engine, tables=[FamilyInvitation.__table__])
                except Exception as ex:
                    logger.warning(f"Native script notice ({ex}), ensuring tables via SQLAlchemy metadata...")
                    Base.metadata.create_all(bind=engine, tables=[FamilyInvitation.__table__])
        else:
            Base.metadata.create_all(bind=engine, tables=[FamilyInvitation.__table__])

        record_migration(engine, version_002, "Family invitations table with codes, expiry and permissions")
        logger.info(f"Migration {version_002} applied successfully.")
    else:
        logger.info(f"Migration {version_002} is already recorded.")

    version_003 = "003_auth_upgrade"
    if version_003 not in applied:
        logger.info(f"Applying migration {version_003}: Google OAuth, account lock, and recovery tokens...")
        is_postgres = "postgresql" in str(engine.url)
        migrations_dir = Path(__file__).resolve().parent / "migrations"
        sql_file = migrations_dir / "003_auth_upgrade.sql"

        if is_postgres and sql_file.exists():
            with open(sql_file, "r", encoding="utf-8") as f:
                sql_content = f.read()
            with engine.begin() as conn:
                try:
                    raw_conn = getattr(conn, "connection", None)
                    if hasattr(raw_conn, "dbapi_connection"):
                        raw_cursor = raw_conn.dbapi_connection.cursor()
                    elif hasattr(raw_conn, "cursor"):
                        raw_cursor = raw_conn.cursor()
                    else:
                        raw_cursor = None

                    if raw_cursor:
                        raw_cursor.execute(sql_content)
                        raw_cursor.close()
                    else:
                        conn.execute(text(sql_content))
                except Exception as ex:
                    logger.warning(f"Native script notice ({ex}), executing statements with SQLAlchemy text...")
                    for stmt in sql_content.split(";"):
                        if stmt.strip():
                            conn.execute(text(stmt.strip()))
        else:
            with engine.begin() as conn:
                # Add columns for SQLite or other engine if needed
                inspector = inspect(engine)
                cols = {c["name"] for c in inspector.get_columns("users")}
                if "google_id" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(128)"))
                if "google_email" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_email VARCHAR(256)"))
                if "failed_login_attempts" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0"))
                if "locked_until" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP"))
                if "recovery_token" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN recovery_token VARCHAR(128)"))
                if "recovery_token_expires_at" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN recovery_token_expires_at TIMESTAMP"))

        record_migration(engine, version_003, "Google OAuth, account lock (brute-force defense), and recovery tokens")
        logger.info(f"Migration {version_003} applied successfully.")
    else:
        logger.info(f"Migration {version_003} is already recorded.")

    # Ensure all columns exist and match schema requirements
    ensure_initial_schema_columns(engine)
    return True

if __name__ == "__main__":
    try:
        run_migrations()
        print("Database migrations applied and verified successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
