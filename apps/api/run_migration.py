#!/usr/bin/env python3
"""Reset and run migrations on Supabase database."""
import os
from urllib.parse import quote

# Set the properly encoded DATABASE_URL BEFORE any imports
password = quote("633085Aa!1@2", safe="")
db_url = f"postgresql://postgres.nanrgavmraaeflwscbuk:{password}@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
os.environ["DATABASE_URL"] = db_url

from sqlalchemy import create_engine, text  # noqa: E402

engine = create_engine(db_url)

print("Cleaning up Supabase database...")
with engine.connect() as conn:
    # Get all user-created tables
    result = conn.execute(text("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename NOT LIKE 'pg_%'
    """))
    tables = [row[0] for row in result]
    
    if tables:
        print(f"Found tables: {tables}")
        # Drop alembic_version first to reset migration state
        if "alembic_version" in tables:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            print("Dropped alembic_version")
        
        # Drop all other tables
        for table in tables:
            if table != "alembic_version":
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                print(f"Dropped {table}")
        conn.commit()
    else:
        print("No tables found")

print("\nRunning all migrations from scratch...")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

alembic_cfg = Config("alembic.ini")
command.upgrade(alembic_cfg, "head")

print("\n✓ All migrations completed successfully!")
