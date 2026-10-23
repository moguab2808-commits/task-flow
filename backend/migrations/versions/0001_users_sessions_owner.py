"""users, sessions 신설과 tasks.owner_id 추가 (이슈 #6, R-009)

기존 Task 는 지우지 않는다. owner_id 외의 값도 바꾸지 않는다.
기존 Task 의 소유자는 이전용 계정 migrated@test.com 이다 (D-016). 이 계정은
password_hash 가 없어 로그인할 수 없고, 이 이름으로 가입하는 사람이 넘겨받는다.

Revision ID: 0001
Revises:
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MIGRATED_USERNAME = "migrated@test.com"


def upgrade() -> None:
    bind = op.get_bind()
    task_columns = [r[1] for r in bind.execute(sa.text("PRAGMA table_info(tasks)"))]
    if "owner_id" in task_columns:
        # init_db 가 새로 만든 DB. 이미 최신 스키마이므로 할 일이 없다.
        return
    if not task_columns:
        raise RuntimeError("tasks 테이블이 없습니다. 서버를 한 번 시작해 DB 를 만든 뒤 실행하세요.")

    op.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    bind.execute(
        sa.text("INSERT INTO users (username, password_hash, created_at) VALUES (:u, NULL, :t)"),
        {"u": MIGRATED_USERNAME, "t": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    )
    op.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
    op.execute(
        f"UPDATE tasks SET owner_id = (SELECT id FROM users WHERE username = '{MIGRATED_USERNAME}')"
    )


def downgrade() -> None:
    raise RuntimeError("되돌리기는 백업 파일로 복원한다 (DATA-MIGRATION-PLAN 6절).")
