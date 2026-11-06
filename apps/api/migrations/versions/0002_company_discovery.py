"""Add company discovery status and normalized job fields."""
import sqlalchemy as sa
from alembic import op

revision = "0002_company_discovery"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("companies", sa.Column("discovery_status", sa.String(length=30), nullable=False, server_default="queued"))
    op.add_column("companies", sa.Column("discovery_error", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("job_openings", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("job_openings", sa.Column("workplace_type", sa.String(length=120), nullable=True))
    op.add_column("job_openings", sa.Column("source", sa.String(length=40), nullable=False, server_default="website"))
    op.add_column("job_openings", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("job_openings", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_company_job_url", "job_openings", ["company_id", "apply_url"])


def downgrade():
    op.drop_constraint("uq_company_job_url", "job_openings", type_="unique")
    op.drop_column("job_openings", "last_seen_at")
    op.drop_column("job_openings", "first_seen_at")
    op.drop_column("job_openings", "source")
    op.drop_column("job_openings", "workplace_type")
    op.drop_column("job_openings", "location")
    op.drop_column("companies", "last_discovered_at")
    op.drop_column("companies", "discovery_error")
    op.drop_column("companies", "discovery_status")
