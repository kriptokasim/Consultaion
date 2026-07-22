"""P161: forward-repair policyless RLS and ambiguous credit reservations.

Revision ID: p161_security_billing
Revises: p160_enable_public_rls
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "p161_security_billing"
down_revision: Union[str, None] = "p160_enable_public_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen inventory of Consultaion-owned public tables that existed when the
# blanket P160 migration shipped.  This list is intentionally explicit: a
# policyless table owned by another application (or deliberately configured as
# default-deny) must never lose RLS merely because it shares the public schema.
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


def _disable_policyless_public_rls() -> None:
    """Undo the historical blanket RLS enable without weakening real policies.

    The old P160 enabled RLS on every public table but created no policies.
    Tables that now have an explicit policy are intentionally left alone.
    """

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    managed_tables_sql = ", ".join(
        f"'{table_name}'" for table_name in P160_MANAGED_PUBLIC_TABLES
    )
    op.execute(sa.text(
        "DO $$ "
        "DECLARE target RECORD; "
        "BEGIN "
        "  FOR target IN "
        "    SELECT n.nspname AS schema_name, c.relname AS table_name "
        "    FROM pg_class AS c "
        "    JOIN pg_namespace AS n ON n.oid = c.relnamespace "
        "    WHERE n.nspname = 'public' "
        "      AND c.relkind IN ('r', 'p') "
        f"      AND c.relname IN ({managed_tables_sql}) "
        "      AND c.relrowsecurity "
        "      AND NOT EXISTS ("
        "        SELECT 1 FROM pg_policy AS p WHERE p.polrelid = c.oid"
        "      ) "
        "  LOOP "
        "    EXECUTE format('ALTER TABLE %I.%I DISABLE ROW LEVEL SECURITY', "
        "                   target.schema_name, target.table_name); "
        "  END LOOP; "
        "END $$"
    ))


def _repair_credit_reservation_states() -> None:
    """Classify only reservations with a provable durable operation identity.

    Anything that cannot be linked to the exact Debate/Continuation reservation
    is quarantined for explicit reconciliation instead of being assumed settled
    or refunded.
    """

    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if bind.dialect.name != "postgresql" or not {
        "usage_ledger_entry",
        "debate",
    }.issubset(tables):
        return

    columns = {
        column["name"] for column in inspector.get_columns("usage_ledger_entry")
    }
    required = {
        "id",
        "kind",
        "status",
        "debate_id",
        "meta",
        "settled_at",
        "refunded_at",
    }
    if not required.issubset(columns):
        return

    # Start fail-closed.  Subsequent statements release only exact, known
    # identities into an automatic terminal or in-flight state.
    op.execute(sa.text(
        "UPDATE usage_ledger_entry "
        "SET status = 'reconciliation_pending' "
        "WHERE kind = 'credit_reservation' "
        "AND NOT (status = 'refunded' AND refunded_at IS NOT NULL) "
        "AND NOT (status = 'settled' AND settled_at IS NOT NULL)"
    ))

    if "debate_continuation" in tables:
        op.execute(sa.text(
            "UPDATE usage_ledger_entry AS ule SET status = 'settled' "
            "FROM debate_continuation AS dc "
            "WHERE ule.kind = 'credit_reservation' "
            "AND NULLIF(ule.meta ->> 'continuation_id', '') = dc.id "
            "AND dc.debate_id = ule.debate_id "
            "AND dc.credit_reservation_id = ule.id "
            "AND dc.status = 'completed' "
            "AND ule.status <> 'refunded'"
        ))
        op.execute(sa.text(
            "UPDATE usage_ledger_entry AS ule SET status = 'reserved' "
            "FROM debate_continuation AS dc "
            "WHERE ule.kind = 'credit_reservation' "
            "AND NULLIF(ule.meta ->> 'continuation_id', '') = dc.id "
            "AND dc.debate_id = ule.debate_id "
            "AND dc.credit_reservation_id = ule.id "
            "AND dc.status IN ('requested', 'preflight_passed', 'dispatched', 'running', 'paused') "
            "AND ule.status NOT IN ('refunded', 'settled')"
        ))

    # Initial reservations are distinguished by the lack of a continuation ID
    # and the exact reservation stored on the Debate row.
    op.execute(sa.text(
        "UPDATE usage_ledger_entry AS ule SET status = 'settled' "
        "FROM debate AS d "
        "WHERE ule.kind = 'credit_reservation' "
        "AND COALESCE(ule.meta ->> 'continuation_id', '') = '' "
        "AND d.id = ule.debate_id "
        "AND d.credit_reservation_id = ule.id "
        "AND d.status IN ('completed', 'completed_with_warnings') "
        "AND ule.status <> 'refunded'"
    ))
    op.execute(sa.text(
        "UPDATE usage_ledger_entry AS ule SET status = 'reserved' "
        "FROM debate AS d "
        "WHERE ule.kind = 'credit_reservation' "
        "AND COALESCE(ule.meta ->> 'continuation_id', '') = '' "
        "AND d.id = ule.debate_id "
        "AND d.credit_reservation_id = ule.id "
        "AND d.status NOT IN ('completed', 'completed_with_warnings', 'failed', 'cancelled') "
        "AND ule.status NOT IN ('refunded', 'settled')"
    ))


def upgrade() -> None:
    _disable_policyless_public_rls()
    _repair_credit_reservation_states()


def downgrade() -> None:
    # Re-enabling policyless blanket RLS or undoing a conservative accounting
    # quarantine would be unsafe.  This forward security repair is one-way.
    pass
