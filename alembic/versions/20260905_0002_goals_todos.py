"""goals, todos

Revision ID: 0002_goals_todos
Revises: 0001_users_refresh_tokens
Create Date: 2026-09-05

손으로 작성했다. app/db/models/goal.py · todo.py 와 1:1 이어야 CI 의 `alembic check` 가 통과한다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_goals_todos"
down_revision: str | None = "0001_users_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("goal_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("frequency_times", sa.SmallInteger(), nullable=True),
        sa.Column("frequency_per", sa.String(length=10), nullable=True),
        sa.Column("duration_weeks", sa.SmallInteger(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("estimated_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("goal_id", name="pk_goals"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.user_id"], name="fk_goals_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint("type IN ('single', 'recurring')", name="type"),
        sa.CheckConstraint("status IN ('active', 'completed', 'archived')", name="status"),
        sa.CheckConstraint(
            "frequency_per IS NULL OR frequency_per IN ('week', 'month')", name="frequency_per"
        ),
        sa.CheckConstraint(
            "type = 'single' OR (frequency_times IS NOT NULL AND frequency_per IS NOT NULL)",
            name="frequency",
        ),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="date_order"),
    )
    op.create_index("ix_goals_user_id_status", "goals", ["user_id", "status"])

    op.create_table(
        "todos",
        sa.Column("todo_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("goal_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("estimated_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("actual_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("display_order", sa.SmallInteger(), nullable=False),
        sa.Column("postpone_count", sa.SmallInteger(), nullable=False),
        sa.Column("memo", sa.String(length=500), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("todo_id", name="pk_todos"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.user_id"], name="fk_todos_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["goals.goal_id"], name="fk_todos_goal_id_goals", ondelete="SET NULL"
        ),
        sa.CheckConstraint("status IN ('pending', 'done', 'deferred', 'skipped')", name="status"),
        sa.CheckConstraint("source IN ('manual', 'ai_suggested', 'auto_scheduled')", name="source"),
    )
    op.create_index(
        "ix_todos_user_id_date_alive",
        "todos",
        ["user_id", "date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_todos_goal_id_status", "todos", ["goal_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_todos_goal_id_status", table_name="todos")
    op.drop_index("ix_todos_user_id_date_alive", table_name="todos")
    op.drop_table("todos")
    op.drop_index("ix_goals_user_id_status", table_name="goals")
    op.drop_table("goals")
