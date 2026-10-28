import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# 이미 설정된 환경 변수는 덮어쓰지 않는다 (테스트 · 실행 환경이 우선).
load_dotenv(ENV_PATH, override=False)


def anthropic_api_key() -> str | None:
    # 없으면 None. AI 기능만 꺼지고 서버는 정상 시작한다. 값은 코드 · 로그에 남기지 않는다.
    return os.environ.get("ANTHROPIC_API_KEY", "").strip() or None


def session_secret() -> str:
    # 값이 비어 있으면 서버를 시작하지 않는다. 값은 코드 · 로그에 남기지 않는다.
    secret = os.environ.get("SESSION_SECRET", "").strip()
    if not secret:
        raise RuntimeError(
            "SESSION_SECRET 이 비어 있습니다. backend/.env 에 값을 설정해 주세요."
        )
    return secret
