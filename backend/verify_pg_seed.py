import os
import sys

# Ensure clean reload of environment and db settings
from app.core.config import settings
print(f"DATABASE_URL: {settings.DATABASE_URL}")
print(f"FALLBACK_SQLITE_IF_NO_PG: {settings.FALLBACK_SQLITE_IF_NO_PG}")

from app.db.session import engine, Base, SessionLocal
from app.db.migrate import run_migrations
from app.database.seed import init_db

print("Checking engine dialect and connection...")
print(f"Engine dialect: {engine.dialect.name}")
assert engine.dialect.name == "postgresql", f"Expected postgresql, got {engine.dialect.name}!"

with engine.connect() as conn:
    print("PostgreSQL connection confirmed active!")

print("Running migrations on PostgreSQL...")
run_migrations(engine)

print("Creating all tables via Base.metadata.create_all...")
Base.metadata.create_all(bind=engine)

print("Seeding database...")
db = SessionLocal()
init_db(db)
db.close()

print("\n>>> POSTGRESQL 18 MIGRATION & SEED VERIFIED SUCCESSFULLY! <<<")
