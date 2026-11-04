"""backend/.env 의 DATABASE_URL 로 연결해 접속 상태를 읽기만 한다 (쓰기 명령 없음).

실행: uv run --with "psycopg[binary]" backend/supabase/db_check.py
psycopg 는 requirements 에 넣지 않고 --with 로만 쓴다. 비밀번호는 출력하지 않는다.
"""
import statistics
import sys
import time
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
TABLES = ("users", "sessions", "tasks")
QUERY_RUNS = 5


def read_database_url() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit(f"{ENV_PATH} 에 DATABASE_URL 이 없습니다.")


def main() -> int:
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    url = read_database_url()
    info = conninfo_to_dict(url)
    host = info.get("host", "?")
    port = str(info.get("port", "5432"))
    kind = {"6543": " (pooler)", "5432": " (direct)"}.get(port, "")

    try:
        started = time.perf_counter()
        conn = psycopg.connect(url)
        connect_ms = (time.perf_counter() - started) * 1000
        try:
            conn.read_only = True
            version = conn.execute("select version()").fetchone()[0]
            role = conn.execute("select current_user").fetchone()[0]

            samples = []
            for _ in range(QUERY_RUNS):
                started = time.perf_counter()
                conn.execute("select 1").fetchone()
                samples.append((time.perf_counter() - started) * 1000)

            rows = conn.execute(
                "select tablename, tableowner, rowsecurity from pg_tables "
                "where schemaname = 'public' and tablename = any(%s)",
                (list(TABLES),),
            ).fetchall()
            conn.rollback()
        finally:
            conn.close()
    except psycopg.Error as e:
        # 메시지에 접속 정보가 섞일 수 있어 예외 종류만 보여 준다.
        print(f"실패: {type(e).__name__}", file=sys.stderr)
        return 1

    short_version = " ".join(version.split()[:2])
    print(f"① host={host}  port={port}{kind}  server={short_version}  role={role}")
    print(f"② connect={connect_ms:.0f}ms  query({QUERY_RUNS}회 중앙값)={statistics.median(samples):.0f}ms")

    found = {name: (owner, rls) for name, owner, rls in rows}
    parts = []
    for name in TABLES:
        if name not in found:
            parts.append(f"{name} 없음")
        else:
            owner, rls = found[name]
            parts.append(f"{name} owner={owner} RLS={'on' if rls else 'off'}")
    print("③ " + " | ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
