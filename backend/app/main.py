import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import init_db
from app.routers import tasks


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="task-flow API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)


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
