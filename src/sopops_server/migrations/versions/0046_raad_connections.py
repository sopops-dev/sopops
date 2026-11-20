"""Fence repository syncs and track recoverable raad proposals."""

from uuid import uuid4
import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("repo_connections") as batch:
        batch.add_column(sa.Column("connection_id", sa.String(32), nullable=True))
        batch.add_column(sa.Column("generation", sa.String(32), nullable=True))
        batch.add_column(sa.Column("pending_request", sa.Text(), nullable=True))
        for name in ("proposal_head", "pending_operation", "pending_digest"):
            batch.add_column(sa.Column(name, sa.String(64), nullable=True))
    db = op.get_bind()
    for ws in (
        db.execute(sa.text("SELECT workspace FROM repo_connections")).scalars().all()
    ):
        db.execute(
            sa.text(
                "UPDATE repo_connections SET connection_id=:id, generation=:gen WHERE workspace=:ws"
            ),
            {"id": uuid4().hex, "gen": uuid4().hex, "ws": ws},
        )
    with op.batch_alter_table("repo_connections") as batch:
        batch.alter_column("connection_id", existing_type=sa.String(32), nullable=False)
        batch.alter_column("generation", existing_type=sa.String(32), nullable=False)


def downgrade():
    with op.batch_alter_table("repo_connections") as batch:
        for name in (
            "pending_request",
            "pending_digest",
            "pending_operation",
            "proposal_head",
            "generation",
            "connection_id",
        ):
            batch.drop_column(name)
