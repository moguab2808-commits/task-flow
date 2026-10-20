from fastapi import APIRouter

from app import repository
from app.schemas import TaskCreate, TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
def list_tasks():
    return repository.list_tasks()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate):
    return repository.create_task(body.title, body.description)
