import os
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger("ever_near.db")
Base = declarative_base()

# Resolve persistent local fallback path deterministically
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
FALLBACK_DB_PATH = BACKEND_DIR / "ever_near.db"
FALLBACK_DB_URL = f"sqlite:///{FALLBACK_DB_PATH.as_posix()}"

def get_engine():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    try:
        if "postgresql" in db_url:
            # Quick network liveness check to avoid multi-second OS connect timeouts
            import socket
            from urllib.parse import urlparse
            host = "127.0.0.1"
            port = 5432
            try:
                parsed = urlparse(db_url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 5432
                with socket.create_connection((host, port), timeout=0.5):
                    pass
            except Exception as se:
                raise ConnectionError(f"PostgreSQL host {host}:{port} is not accepting connections: {se}")

            # Try connecting to PostgreSQL
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"connect_timeout": 3}
            )
            # Test connection
            with engine.connect() as conn:
                logger.info("Successfully connected to PostgreSQL database.")
                return engine
    except Exception as e:
        if settings.FALLBACK_SQLITE_IF_NO_PG and not settings.is_production:
            logger.info(f"Falling back to local development relational database ({FALLBACK_DB_URL})")
            return create_engine(FALLBACK_DB_URL, connect_args={"check_same_thread": False})
        raise RuntimeError(f"PostgreSQL connection to {settings.DATABASE_URL} failed: {e}. Fallback to SQLite is strictly disabled in production.")

    if db_url.startswith("sqlite"):
        return create_engine(db_url, connect_args={"check_same_thread": False})
    
    return create_engine(FALLBACK_DB_URL, connect_args={"check_same_thread": False})

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
