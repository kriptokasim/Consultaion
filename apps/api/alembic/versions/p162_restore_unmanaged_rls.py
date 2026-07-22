"""P162: explicitly review and restore unmanaged RLS state after P161.

Revision ID: p162_restore_unmanaged_rls
Revises: p161_security_billing

The first published P161 revision disabled RLS on every policyless table in the
public schema.  Editing that already-applied revision cannot repair existing
databases, and the prior RLS state of an unmanaged table cannot be inferred
safely.  This forward migration therefore stops on ambiguous tables until an
operator supplies an explicit deployment inventory.
"""

from __future__ import annotations

import os
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p162_restore_unmanaged_rls"
down_revision: Union[str, None] = "p161_security_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_REVIEWED_ENV = "P162_RLS_REVIEWED"
RLS_RESTORE_TABLES_ENV = "P162_RLS_RESTORE_TABLES"

# Frozen copy of the P160/P161 Consultaion-owned table inventory.  Alembic
# revisions must remain self-contained: a future edit to application metadata
# must not change what this historical repair considers unmanaged.
P160_MANAGED_PUBLIC_TABLES = (
    "admin_event",
    "alembic_version",
    "api_key",
    "api_keys",
    "audit_log",
    "billing_plans",
    "billing_reconciliation_discrepancies",
    "billing_reconciliation_runs",
    "billing_subscriptions",
    "billing_usage",
    "billing_webhook_events",
    "challenge_round",
    "challenge_session",
    "coding_lane_result",
    "coding_patch_artifact",
    "coding_run",
    "coding_turn",
    "conversation_votes",
    "debate",
    "debate_attempt",
    "debate_checkpoint",
    "debate_continuation",
    "debate_error",
    "debate_stage_checkpoint",
    "debate_turn",
    "debateround",
    "divergence_report",
    "llm_usage_log",
    "message",
    "oracle_branch",
    "oracle_session",
    "pairwise_vote",
    "promotions",
    "rating_persona",
    "red_team_session",
    "score",
    "support_note",
    "team",
    "team_member",
    "team_member_dedup_audit",
    "terminal_transition",
    "usage_counter",
    "usage_ledger_entry",
    "usage_quota",
    "user",
    "user_interaction",
    "user_prediction",
    "user_provider_keys",
    "vote",
    "vote_record",
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _parse_restore_inventory(raw: str | None) -> tuple[str, ...]:
    names: list[str] = []
    for value in (raw or "").split(","):
        name = value.strip()
        if not name:
            continue
        if name.startswith("public."):
            name = name.removeprefix("public.")
        if not _IDENTIFIER.fullmatch(name):
            raise RuntimeError(
                f"Invalid table name in {RLS_RESTORE_TABLES_ENV}: {value!r}"
            )
        if name not in names:
            names.append(name)
    return tuple(names)


def _ambiguous_unmanaged_tables(bind) -> tuple[str, ...]:
    managed_tables_sql = ", ".join(
        f"'{table_name}'" for table_name in P160_MANAGED_PUBLIC_TABLES
    )
    result = bind.execute(sa.text(
        "SELECT c.relname "
        "FROM pg_class AS c "
        "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' "
        "AND c.relkind IN ('r', 'p') "
        "AND NOT c.relrowsecurity "
        f"AND c.relname NOT IN ({managed_tables_sql}) "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM pg_policy AS p WHERE p.polrelid = c.oid"
        ") "
        "ORDER BY c.relname"
    ))
    return tuple(result.scalars().all())


def _table_rls_enabled(bind, table_name: str) -> bool | None:
    return bind.execute(
        sa.text(
            "SELECT c.relrowsecurity "
            "FROM pg_class AS c "
            "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' "
            "AND c.relkind IN ('r', 'p') "
            "AND c.relname = :table_name"
        ),
        {"table_name": table_name},
    ).scalar_one_or_none()


def _restore_reviewed_tables(bind, restore_tables: tuple[str, ...]) -> None:
    managed = set(P160_MANAGED_PUBLIC_TABLES)
    for table_name in restore_tables:
        if table_name in managed:
            raise RuntimeError(
                f"{table_name!r} is Consultaion-managed and must not be listed in "
                f"{RLS_RESTORE_TABLES_ENV}"
            )
        current_state = _table_rls_enabled(bind, table_name)
        if current_state is None:
            raise RuntimeError(
                f"Table public.{table_name} from {RLS_RESTORE_TABLES_ENV} does not exist"
            )
        if not current_state:
            quoted = bind.dialect.identifier_preparer.quote_identifier(table_name)
            bind.execute(sa.text(
                f"ALTER TABLE public.{quoted} ENABLE ROW LEVEL SECURITY"
            ))
        if _table_rls_enabled(bind, table_name) is not True:
            raise RuntimeError(
                f"Failed to restore RLS on reviewed table public.{table_name}"
            )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    ambiguous = _ambiguous_unmanaged_tables(bind)
    restore_tables = _parse_restore_inventory(
        os.getenv(RLS_RESTORE_TABLES_ENV)
    )
    reviewed = os.getenv(RLS_REVIEWED_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    if (ambiguous or restore_tables) and not reviewed:
        candidate_list = ", ".join(f"public.{name}" for name in ambiguous) or "none"
        raise RuntimeError(
            "P162 cannot infer the pre-P161 RLS state of unmanaged tables. "
            f"Review these disabled policyless tables: {candidate_list}. "
            f"Set {RLS_REVIEWED_ENV}=1 and list every table that must regain RLS "
            f"in {RLS_RESTORE_TABLES_ENV}. Use an empty restore list only after "
            "confirming that all candidates are intentionally unprotected."
        )

    if reviewed:
        _restore_reviewed_tables(bind, restore_tables)


def downgrade() -> None:
    # Disabling a protection explicitly restored by an operator is unsafe.
    pass
