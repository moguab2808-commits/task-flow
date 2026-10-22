from fastapi import APIRouter, Cookie, Depends, HTTPException, Response

from app import auth_repository, security
from app.deps import COOKIE_NAME, get_current_user
from app.schemas import LoginIn, SignupIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

DUPLICATE = "이미 쓰는 사용자 이름입니다."
BAD_LOGIN = "사용자 이름 또는 비밀번호가 맞지 않습니다."

# 없는 사용자 이름과 있는 이름의 응답 시간이 달라지지 않게 쓰는 값.
_DUMMY_HASH = security.hash_password("dummy-password")


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(body: SignupIn):
    if not auth_repository.create_user(body.username, security.hash_password(body.password)):
        raise HTTPException(status_code=409, detail=DUPLICATE)
    return UserOut(username=body.username)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response):
    user = auth_repository.find_user_by_username(body.username)
    stored = user["password_hash"] if user else _DUMMY_HASH
    ok = security.verify_password(body.password, stored)
    if user is None or not ok:
        raise HTTPException(status_code=401, detail=BAD_LOGIN)
    session_id = security.new_session_id()
    auth_repository.create_session(session_id, user["id"])
    response.set_cookie(
        COOKIE_NAME,
        security.sign_session_id(session_id),
        max_age=int(auth_repository.SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=False,  # 로컬 http 에서만 쓴다
        path="/",
    )
    return UserOut(username=user["username"])


@router.post("/logout", status_code=204)
def logout(taskflow_session: str | None = Cookie(default=None)):
    session_id = security.read_session_cookie(taskflow_session)
    if session_id:
        auth_repository.delete_session(session_id)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(username=user["username"])
