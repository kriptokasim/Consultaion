import argparse
import os
import sys
from urllib.parse import urlparse, urlunparse

# Ensure the PostgreSQL driver is available
try:
    import psycopg2  # noqa: F401
except ImportError:
    print("⚠️  psycopg2 driver not installed. Install it with 'pip install psycopg2-binary' before using dev_db utilities.")
    sys.exit(1)

from alembic import command
from alembic.config import Config
from config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError


# Helper to build Alembic config
def get_alembic_config() -> Config:
    # Alembic expects a path to alembic.ini; we use the one in apps/api
    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg = Config(alembic_ini_path)
    # Override the sqlalchemy.url with current DATABASE_URL
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return cfg

# Parse DATABASE_URL to extract components for admin connection
def parse_db_url(db_url: str):
    # Expected format: postgresql+psycopg://user:pass@host:port/dbname
    parsed = urlparse(db_url)
    scheme = parsed.scheme.split("+")[0]  # strip driver suffix
    username = parsed.username or ""
    password = parsed.password or ""
    host = parsed.hostname or "localhost"
    port = str(parsed.port) if parsed.port else "5432"
    db_name = parsed.path.lstrip("/")
    return scheme, username, password, host, port, db_name

def get_admin_url():
    # Preserve full scheme (including driver) from DATABASE_URL
    from urllib.parse import urlparse
    parsed = urlparse(settings.DATABASE_URL)
    scheme = parsed.scheme  # e.g., "postgresql+psycopg"
    user = parsed.username or ""
    pwd = parsed.password or ""
    host = parsed.hostname or "localhost"
    port = str(parsed.port) if parsed.port else "5432"
    admin_db = "postgres"
    netloc = f"{user}:{pwd}@{host}:{port}" if user else f"{host}:{port}"
    admin_url = urlunparse((scheme, netloc, f"/{admin_db}", "", "", ""))
    return admin_url

def run_migrations():
    cfg = get_alembic_config()
    command.upgrade(cfg, "head")
    print("✅ Migrations applied successfully.")

def reset_and_migrate():
    if not settings.IS_LOCAL_ENV:
        print("⚠️  reset-and-migrate is only allowed in local/dev environments.")
        sys.exit(1)
    # Connect to admin DB to drop/create target DB
    admin_url = get_admin_url()
    admin_engine = create_engine(admin_url)
    _, _, _, _, _, target_db = parse_db_url(settings.DATABASE_URL)
    # Use autocommit to allow DROP DATABASE outside a transaction
    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        # Terminate connections (Postgres >=13 supports FORCE)
        try:
            conn.execute(text(f"DROP DATABASE IF EXISTS {target_db} WITH (FORCE);"))
        except ProgrammingError:
            # Fallback for older versions: terminate backends then drop
            conn.execute(text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :dbname;"
            ), {"dbname": target_db})
            conn.execute(text(f"DROP DATABASE IF EXISTS {target_db};"))
        conn.execute(text(f"CREATE DATABASE {target_db};"))
        print(f"✅ Database '{target_db}' recreated.")
    # Run migrations on the fresh DB
    run_migrations()

def verify_schema():
    engine = create_engine(settings.DATABASE_URL)
    critical_tables = [
        "user",
        "team_member",
        "usage_quota",
        "usage_counter",
        "api_keys",
        "audit_log",
        "debate",
    ]
    missing = []
    # Use autocommit to avoid transaction issues during verification
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for tbl in critical_tables:
            try:
                conn.execute(text(f"SELECT 1 FROM {tbl} LIMIT 1;"))
            except (ProgrammingError, OperationalError):
                missing.append(tbl)
    if missing:
        print("❌ Schema verification failed. Missing tables:")
        for tbl in missing:
            print(f"  - {tbl}")
        print("\nRun `python -m scripts.dev_db migrate` or `reset-and-migrate` to fix.")
        sys.exit(1)
    else:
        print("✅ All critical tables are present.")

def seed_demo():
    # Simple demo seeding: create a demo user and a demo API key if not exists.
    from datetime import datetime

    from models import APIKey, User
    from sqlmodel import Session, select
    engine = create_engine(settings.DATABASE_URL)
    demo_email = "demo@example.com"
    demo_password_hash = "demo"  # In real code you'd hash; this is placeholder.
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == demo_email)).first()
        if not user:
            user = User(email=demo_email, password_hash=demo_password_hash, role="user")
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"✅ Demo user created (id={user.id}).")
        else:
            print("ℹ️ Demo user already exists.")
        # Create API key if none
        existing_key = session.exec(select(APIKey).where(APIKey.user_id == user.id)).first()
        if not existing_key:
            # Simple deterministic key for demo purposes
            key = APIKey(
                user_id=user.id,
                name="demo-key",
                prefix="demo",
                hashed_key="demohashed",
                created_at=datetime.utcnow(),
            )
            session.add(key)
            session.commit()
            print("✅ Demo API key created.")
        else:
            print("ℹ️ Demo API key already exists.")

def main():
    parser = argparse.ArgumentParser(description="Development DB utility script")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("migrate", help="Run Alembic migrations to head")
    subparsers.add_parser("reset-and-migrate", help="Drop and recreate DB, then migrate (dev only)")
    subparsers.add_parser("verify", help="Verify critical tables exist")
    subparsers.add_parser("seed-demo", help="Create demo user and API key (idempotent)")

    args = parser.parse_args()
    if args.command == "migrate":
        run_migrations()
    elif args.command == "reset-and-migrate":
        reset_and_migrate()
    elif args.command == "verify":
        verify_schema()
    elif args.command == "seed-demo":
        seed_demo()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
