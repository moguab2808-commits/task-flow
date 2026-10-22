import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import session_secret
from app.db import init_db
from app.routers import auth, tasks


@asynccontextmanager
async def lifespan(_: FastAPI):
    session_secret()  # 값이 비어 있으면 여기서 시작을 거절한다.
    init_db()
    yield


app = FastAPI(title="task-flow API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,  # 세션 쿠키를 주고받는다. 출처는 위 두 곳으로만 제한한다.
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)


@app.exception_handler(RequestValidationError)
def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # 기본 응답은 입력값("input")을 되돌려 준다. 비밀번호가 응답에 담기지 않게 뺀다.
    detail = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": detail}))


@app.exception_handler(sqlite3.Error)
def storage_error(_: Request, __: sqlite3.Error) -> JSONResponse:
    # 저장소 쓰기·읽기 실패: 변경은 일어나지 않은 것으로 알린다.
    return JSONResponse(
        status_code=500,
        content={"detail": "저장소 오류로 처리하지 못했습니다. 다시 시도해 주세요."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
