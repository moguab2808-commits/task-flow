from fastapi import APIRouter, HTTPException

from app import repository
from app.schemas import StatusChange, TaskCreate, TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
def list_tasks():
    return repository.list_tasks()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate):
    return repository.create_task(body.title, body.description)


@router.patch("/{task_id}", response_model=TaskOut)
def change_status(task_id: int, body: StatusChange):
    task = repository.update_status(task_id, body.status)
    if task is None:
        raise HTTPException(status_code=404, detail="이미 없는 카드입니다.")
    return task
