from fastapi import Cookie, HTTPException

from app import auth_repository, security

COOKIE_NAME = "taskflow_session"
UNAUTHORIZED = "로그인이 필요합니다."


def get_current_user(
    taskflow_session: str | None = Cookie(default=None),
) -> dict:
    session_id = security.read_session_cookie(taskflow_session)
    user = auth_repository.find_user_by_session(session_id) if session_id else None
    if user is None:
        raise HTTPException(status_code=401, detail=UNAUTHORIZED)
    return user
