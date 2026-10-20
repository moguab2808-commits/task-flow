from fastapi import APIRouter, Body, HTTPException, Response
from pydantic import ValidationError

from app import repository
from app.schemas import ContentChange, StatusChange, TaskCreate, TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

NOT_FOUND = "이미 없는 카드입니다."


@router.get("", response_model=list[TaskOut])
def list_tasks():
    return repository.list_tasks()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate):
    return repository.create_task(body.title, body.description)


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(task_id: int, body: dict = Body(...)):
    # 상태 변경과 내용 수정은 서로 다른 동작이다. 섞인 요청은 거절한다 (D-004).
    if "status" in body:
        model: type[StatusChange] | type[ContentChange] = StatusChange
    else:
        model = ContentChange
    try:
        parsed = model.model_validate(body)
    except ValidationError as e:
        detail = [{"loc": list(err["loc"]), "msg": err["msg"]} for err in e.errors()]
        raise HTTPException(status_code=422, detail=detail) from e
    if isinstance(parsed, StatusChange):
        task = repository.update_status(task_id, parsed.status)
    else:
        task = repository.update_content(task_id, parsed.title, parsed.description)
    if task is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int):
    if not repository.delete_task(task_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)
