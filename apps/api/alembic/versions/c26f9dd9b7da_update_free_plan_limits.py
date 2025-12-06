"""update_free_plan_limits

Revision ID: c26f9dd9b7da
Revises: dcdade8ec015
Create Date: 2025-12-06 08:30:36.570223

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c26f9dd9b7da"
down_revision: Union[str, None] = "dcdade8ec015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    is_postgres = dialect_name == "postgresql"
    
    # Update the Free plan limits
    # We use a JSON update if possible, or a full replace
    if is_postgres:
        op.execute("""
            UPDATE billing_plans 
            SET limits = jsonb_set(limits::jsonb, '{max_debates_per_month}', '5')::json 
            WHERE slug = 'free';
        """)
    else:
        # SQLite fallback (replace entire json)
        # Note: This assumes we know the other limits. 
        # Since we just seeded it, we know it was {max_debates: 10, max_models: 3, exports: False}
        # We update it to {max_debates: 5, ...}
        op.execute("""
            UPDATE billing_plans 
            SET limits = '{"max_debates_per_month": 5, "max_models_per_debate": 3, "exports_enabled": false}'
            WHERE slug = 'free';
        """)


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    is_postgres = dialect_name == "postgresql"
    
    if is_postgres:
        op.execute("""
            UPDATE billing_plans 
            SET limits = jsonb_set(limits::jsonb, '{max_debates_per_month}', '10')::json 
            WHERE slug = 'free';
        """)
    else:
        op.execute("""
            UPDATE billing_plans 
            SET limits = '{"max_debates_per_month": 10, "max_models_per_debate": 3, "exports_enabled": false}'
            WHERE slug = 'free';
        """)
