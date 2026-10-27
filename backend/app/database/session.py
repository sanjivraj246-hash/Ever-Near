# Re-export from app.db.session for backward compatibility
from app.db.session import engine, SessionLocal, Base, get_db, get_engine, FALLBACK_DB_URL, FALLBACK_DB_PATH

__all__ = ["engine", "SessionLocal", "Base", "get_db", "get_engine", "FALLBACK_DB_URL", "FALLBACK_DB_PATH"]
