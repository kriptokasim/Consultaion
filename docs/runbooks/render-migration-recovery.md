# Render Migration Recovery

If a Render deployment fails due to a locked migration or schema drift, use `migrate_database.py` to recover.

## Diagnosis
The `start_production.sh` start command runs `migrate_database.py --check`. If this fails, the web server will crash. This usually indicates that the Render Release command (`python scripts/migrate_database.py`) failed or was interrupted.

## Recovery via SSH / Shell
Connect to the Render Shell for the service:

1. Check current state:
   ```bash
   python scripts/migrate_database.py --check
   ```

2. Perform break-glass stamping if you are certain the DB schema matches the intended revision:
   ```bash
   python scripts/migrate_database.py --allow-stamp --expected-current <OLD_REV> --stamp <NEW_REV>
   ```

3. Re-deploy the service once fixed.
