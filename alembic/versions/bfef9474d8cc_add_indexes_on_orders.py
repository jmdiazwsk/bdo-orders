"""add indexes on orders

Revision ID: bfef9474d8cc
Revises: c62fa3621d55
Create Date: 2025-09-28 09:33:06.860120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfef9474d8cc'
down_revision: Union[str, Sequence[str], None] = 'c62fa3621d55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    # No-op: los índices ya se crean en la migración inicial a partir del modelo.
    pass

def downgrade():
    pass