"""tasks 에 priority, due_date 추가 (이슈 #21, R-010, R-011)

기존 Task 는 지우지 않는다. 새 두 열 외의 값은 바꾸지 않는다 (updated_at 도 그대로).
이미 있는 Task 는 priority NORMAL, due_date 없음(NULL)이 된다.
downgrade 는 만들지 않는다. 되돌리기는 백업 파일로 복원한다 (DATA-MIGRATION-PLAN 6절).

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    task_columns = [r[1] for r in bind.execute(sa.text("PRAGMA table_info(tasks)"))]
    if "priority" in task_columns:
        # init_db 가 새로 만든 DB. 이미 최신 스키마이므로 할 일이 없다.
        return

    op.execute(
        "ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'NORMAL'"
        " CHECK (priority IN ('LOW', 'NORMAL', 'HIGH'))"
    )
    op.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
