"""P159: durable initial credit identity and unique team membership."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "p159_billing_team_integrity"
down_revision: Union[str, None] = "ps158_message_response_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    debate_columns = {c["name"] for c in inspector.get_columns("debate")}
    debate_indexes = {i["name"] for i in inspector.get_indexes("debate")}
    if "credit_reservation_id" not in debate_columns:
        op.add_column(
            "debate", sa.Column("credit_reservation_id", sa.String(), nullable=True)
        )
    if "ix_debate_credit_reservation_id" not in debate_indexes:
        op.create_index(
            "ix_debate_credit_reservation_id", "debate",
            ["credit_reservation_id"], unique=False,
        )

    # Collapse historical duplicates while preserving their strongest role.
    op.execute(sa.text(
        "UPDATE team_member SET role = 'owner' WHERE id IN ("
        "SELECT MIN(id) FROM team_member GROUP BY team_id, user_id "
        "HAVING SUM(CASE WHEN role = 'owner' THEN 1 ELSE 0 END) > 0)"
    ))
    op.execute(sa.text(
        "UPDATE team_member SET role = 'editor' WHERE role <> 'owner' AND id IN ("
        "SELECT MIN(id) FROM team_member GROUP BY team_id, user_id "
        "HAVING SUM(CASE WHEN role = 'editor' THEN 1 ELSE 0 END) > 0)"
    ))
    op.execute(sa.text(
        "DELETE FROM team_member WHERE id NOT IN ("
        "SELECT MIN(id) FROM team_member GROUP BY team_id, user_id)"
    ))
    team_indexes = {i["name"] for i in inspect(bind).get_indexes("team_member")}
    if "uq_team_member_team_user" not in team_indexes:
        op.create_index(
            "uq_team_member_team_user", "team_member",
            ["team_id", "user_id"], unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "uq_team_member_team_user" in {
        i["name"] for i in inspector.get_indexes("team_member")
    }:
        op.drop_index("uq_team_member_team_user", table_name="team_member")
    if "ix_debate_credit_reservation_id" in {
        i["name"] for i in inspect(bind).get_indexes("debate")
    }:
        op.drop_index("ix_debate_credit_reservation_id", table_name="debate")
    if "credit_reservation_id" in {
        c["name"] for c in inspect(bind).get_columns("debate")
    }:
        op.drop_column("debate", "credit_reservation_id")
