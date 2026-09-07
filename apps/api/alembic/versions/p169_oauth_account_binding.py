"""Add federated-merge protection columns to user.

Guards against the pre-hijack pattern: an attacker registers victim@example.com
through /auth/register (which requires no proof of mailbox ownership) and keeps
the password; when the real owner later signs in with Google, the OAuth callback
matches on the bare email and logs them into the attacker's row.

Existing rows are backfilled as verified. They predate this control and there is
no way to tell retroactively which ones were self-registered, so treating them
as trusted keeps every current account working exactly as it does today; the
protection applies from here forward.

Revision ID: p169_oauth_account_binding
Revises: p168_alembic_version_pk
"""
from alembic import op
import sqlalchemy as sa

revision = "p169_oauth_account_binding"
down_revision = "p168_alembic_version_pk"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return any(col["name"] == column for col in inspector.get_columns(table))
    except Exception:
        return False


def upgrade() -> None:
    # Added with server defaults so the ALTER does not rewrite the table and so
    # rows inserted by an older process mid-deploy still satisfy NOT NULL.
    if not _has_column("user", "email_verified_at"):
        op.add_column(
            "user",
            sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column("user", "password_login_enabled"):
        op.add_column(
            "user",
            sa.Column(
                "password_login_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )
    if not _has_column("user", "oauth_provider"):
        op.add_column(
            "user", sa.Column("oauth_provider", sa.String(length=32), nullable=True)
        )

    # Backfill: every account that exists before this migration keeps password
    # login and is treated as verified, so nobody is locked out by the deploy.
    op.execute(
        sa.text(
            "UPDATE \"user\" SET email_verified_at = CURRENT_TIMESTAMP "
            "WHERE email_verified_at IS NULL"
        )
    )


def downgrade() -> None:
    for column in ("oauth_provider", "password_login_enabled", "email_verified_at"):
        if _has_column("user", column):
            op.drop_column("user", column)
