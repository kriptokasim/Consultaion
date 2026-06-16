# Render Migration Recovery

Recovery steps when a database migration fails during Render deployment.

## Before Starting

- Take a database snapshot or backup via Render Dashboard → Databases → Backups
- Have a second person available for review of break-glass steps
- If unsure, pause and document current state first

## Recovery Steps

### 1. Take a database snapshot

Render Dashboard → Your Database → Backups → Create Manual Backup

### 2. Run schema diagnostic

```bash
python scripts/render-schema-diagnostic.py
```

This prints current revision, expected head, and lists missing tables/columns.

### 3. Confirm current revision

From the diagnostic output, note the `Current revision(s)` value.

If it matches the expected head but tables/columns are still missing, there may be a partial migration. Proceed with caution.

### 4. Run safe migration runner

```bash
python apps/api/scripts/migrate_database.py
```

This widens the version column if needed, runs pending migrations, and verifies the result.

### 5. Verify current equals head

```bash
python apps/api/scripts/migrate_database.py --check
```

Or confirm via the `/readyz` endpoint returning 200.

### 6. Verify existing Run count before and after

```sql
SELECT COUNT(*) FROM debate;
SELECT COUNT(*) FROM message;
```

Confirm no data loss.

### 7. Verify one historical Run manually

Fetch a completed run via the API:

```bash
curl -H "Authorization: Bearer <token>" https://consultaion.onrender.com/debates/<run-id>
```

Confirm the response includes the prompt, status, and final_content.

### 8. Restart API

Trigger a deploy in Render Dashboard → API Service → Manual Deploy → Clear build cache & deploy

### 9. Verify /readyz

```bash
curl -s https://consultaion.onrender.com/readyz | python -m json.tool
```

Expected: `{"status": "ready", ...}`

### 10. Verify frontend Run list and Run detail

- Navigate to the Runs list page
- Confirm at least one completed Run renders correctly
- Confirm a historical Run without new workspace metadata opens correctly

## Break-Glass Recovery (--allow-stamp)

Only use when the database revision value is unknown or the migration graph
has been reset, and you have verified the schema is correct.

```bash
python apps/api/scripts/migrate_database.py \
  --allow-stamp \
  --expected-current <exact-current-revision> \
  --stamp <target-revision>
```

Requirements:

- `--expected-current` must match the actual current revision exactly
- This logs an audit warning and prints a backup reminder
- This must not run automatically — only manual invocation

## Do NOT

- Delete the production database as a recovery step
- Drop the `alembic_version` table
- Run `alembic stamp head` without understanding the current state
- Rename applied migration revision IDs
- Recreate the database from scratch
