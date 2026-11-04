"""backend/.env 의 DATABASE_URL 로 연결해 schema.sql 을 한 번 실행하고 테이블별 주인 · RLS 를 출력한다.

실행: uv run --with "psycopg[binary]" backend/supabase/apply_schema.py
psycopg 는 requirements 에 넣지 않고 --with 로만 쓴다. 비밀번호는 출력하지 않는다.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_PATH = HERE.parent / ".env"
SCHEMA_PATH = HERE / "schema.sql"
TABLES = ("users", "sessions", "tasks")


def read_database_url() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit(f"{ENV_PATH} 에 DATABASE_URL 이 없습니다.")


def main() -> int:
    import psycopg

    url = read_database_url()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    try:
        with psycopg.connect(url) as conn:
            conn.execute(schema)
            rows = conn.execute(
                "select tablename, tableowner, rowsecurity from pg_tables "
                "where schemaname = 'public' and tablename = any(%s)",
                (list(TABLES),),
            ).fetchall()
    except psycopg.Error as e:
        # 메시지에 접속 정보가 섞일 수 있어 예외 종류만 보여 준다.
        print(f"실패: {type(e).__name__}", file=sys.stderr)
        return 1

    found = {name: (owner, rls) for name, owner, rls in rows}
    for name in TABLES:
        if name not in found:
            print(f"{name:<9} 없음")
            continue
        owner, rls = found[name]
        print(f"{name:<9} owner={owner}  RLS={'on' if rls else 'off'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
