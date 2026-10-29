from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import ValidationError

from app import briefing, repository, suggest, weekplan
from app.deps import get_current_user
from app.schemas import (
    BriefingOut,
    ContentChange,
    StatusChange,
    SuggestIn,
    SuggestOptionsIn,
    SuggestOptionsOut,
    SuggestOut,
    TaskCreate,
    TaskOut,
    WeekplanOut,
)

# 라우터 전체가 로그인을 요구한다. 401 확인이 입력 검증 · 소유 확인보다 먼저다.
router = APIRouter(
    prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)]
)

NOT_FOUND = "이미 없는 카드입니다."


@router.get("", response_model=list[TaskOut])
def list_tasks(user: dict = Depends(get_current_user)):
    return repository.list_tasks(user["id"])


@router.post("", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, user: dict = Depends(get_current_user)):
    return repository.create_task(
        user["id"], body.title, body.description, body.priority, body.due_date
    )


@router.post("/suggest", response_model=SuggestOut)
def suggest_task(body: SuggestIn):
    # 제안만 돌려준다. 저장하지 않고 DB 도 건드리지 않는다.
    try:
        return suggest.suggest(body.title, body.description)
    except suggest.SuggestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/suggest-options", response_model=SuggestOptionsOut)
def suggest_task_options(body: SuggestOptionsIn):
    # 후보만 돌려준다. 저장하지 않고 DB 도 건드리지 않는다.
    try:
        return suggest.suggest_options(body.title)
    except suggest.SuggestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/briefing", response_model=BriefingOut)
def briefing_today(user: dict = Depends(get_current_user)):
    # 브리핑만 돌려준다. 저장하지 않고 DB 도 바꾸지 않는다.
    try:
        return briefing.briefing(user["id"])
    except suggest.SuggestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/weekplan", response_model=WeekplanOut)
def weekplan_week(user: dict = Depends(get_current_user)):
    # 계획만 돌려준다. 저장하지 않고 DB 도 바꾸지 않는다.
    try:
        return weekplan.weekplan(user["id"])
    except suggest.SuggestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(
    task_id: int, body: dict = Body(...), user: dict = Depends(get_current_user)
):
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
        task = repository.update_status(user["id"], task_id, parsed.status)
    else:
        task = repository.update_content(
            user["id"],
            task_id,
            parsed.title,
            parsed.description,
            parsed.priority,
            # 보내지 않은 due_date 는 그대로 두고, null 이면 지운다.
            parsed.due_date if "due_date" in parsed.model_fields_set else repository.UNSET,
        )
    if task is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, user: dict = Depends(get_current_user)):
    if not repository.delete_task(user["id"], task_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)
