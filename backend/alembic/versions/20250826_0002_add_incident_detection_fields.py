"""add incident detection fingerprint fields

Revision ID: 20250826_0002
Revises: 20250721_0001
Create Date: 2025-08-26 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250826_0002"
down_revision: Union[str, None] = "20250721_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("fingerprint", sa.String(length=256), nullable=True))
    op.add_column("incidents", sa.Column("detection_rule", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_incidents_fingerprint"), "incidents", ["fingerprint"], unique=False)
    op.create_index(op.f("ix_incidents_detection_rule"), "incidents", ["detection_rule"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_incidents_detection_rule"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_fingerprint"), table_name="incidents")
    op.drop_column("incidents", "detection_rule")
    op.drop_column("incidents", "fingerprint")
