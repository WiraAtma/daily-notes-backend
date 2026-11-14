"""Replace Google identity with email/password credentials.

Revision ID: 0002_email_password
Revises: 0001_users_notes
Create Date: 2026-11-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_email_password"
down_revision: Union[str, None] = "0001_users_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=False),
    )
    op.drop_constraint("uq_users_google_id", "users", type_="unique")
    op.drop_column("users", "google_id")


def downgrade() -> None:
    connection = op.get_bind()
    user_count = connection.execute(
        sa.select(sa.func.count()).select_from(sa.table("users"))
    ).scalar_one()
    if user_count:
        raise RuntimeError(
            "Cannot restore Google login after users have registered with passwords."
        )

    op.add_column(
        "users",
        sa.Column("google_id", sa.String(length=255), nullable=False),
    )
    op.create_unique_constraint("uq_users_google_id", "users", ["google_id"])
    op.drop_column("users", "password_hash")
