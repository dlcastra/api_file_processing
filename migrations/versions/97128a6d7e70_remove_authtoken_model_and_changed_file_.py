"""Remove AuthToken model and changed File model

Revision ID: 97128a6d7e70
Revises: baf26b7b895f
Create Date: 2025-01-18 12:13:15.356612

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "97128a6d7e70"
down_revision: Union[str, None] = "baf26b7b895f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_auth_tokens_id", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_key", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.add_column("files", sa.Column("s3_url", sa.String(), nullable=False))
    op.drop_column("files", "file_path")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("files", sa.Column("file_path", sa.VARCHAR(), autoincrement=False, nullable=False))
    op.drop_column("files", "s3_url")
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("key", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("user_agent", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column("user_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="auth_tokens_user_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="auth_tokens_pkey"),
    )
    op.create_index("ix_auth_tokens_key", "auth_tokens", ["key"], unique=True)
    op.create_index("ix_auth_tokens_id", "auth_tokens", ["id"], unique=False)
    # ### end Alembic commands ###
