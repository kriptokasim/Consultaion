#!/usr/bin/env bash
# check-schema-drift.sh — Detect real schema drift by comparing SQLModel metadata
# against Alembic migration head using compare_metadata().
# Exit 0 if in sync, exit 1 if drift detected.
set -euo pipefail

echo "Checking for real schema drift (metadata vs migrations)..."

python3 -c "
import sys
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine
from sqlmodel import SQLModel

# Import all models to register them with SQLModel metadata
import models
import billing.models

config = Config('alembic.ini')
url = config.get_main_option('database_url')
if not url:
    print('ERROR: No database_url in alembic.ini')
    sys.exit(1)

engine = create_engine(url)
with engine.connect() as conn:
    context = MigrationContext.configure(conn)
    diff = compare_metadata(context, SQLModel.metadata)

if diff:
    print('ERROR: Schema drift detected! Model metadata differs from migrations:')
    for item in diff:
        print(f'  {item}')
    sys.exit(1)
else:
    print('OK: SQLModel metadata matches Alembic migrations. No drift.')
    sys.exit(0)
"
