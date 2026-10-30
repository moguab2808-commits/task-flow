"""한 문장으로 시키기: 문장 하나를 add · due · done 동작 목록으로 바꾼다. Claude 를 호출만 한다.

저장소는 읽기만 하고 쓰지 않는다. 동작은 제안일 뿐 실행하지 않고, 삭제 동작은 없다.
모으기 · 호출 · 오류 변환은 briefing · suggest 모듈의 것을 그대로 쓴다.
"""

import json
from datetime import date

from app.briefing import _is_id, _open_tasks
from app.schemas import PRIORITIES, check_due_date
from app.suggest import FAILED, SuggestError, _ask, _load_object

MAX_TOKENS = 600
KINDS = ("add", "due", "done")
ASK_FALLBACK = "무엇을 하라는 말씀인지 알아듣지 못했어요. 다시 말씀해 주세요."

# TODO(사용자 제공 필요): 프롬프트 문구는 사용자가 준 것이 아니라 임시 초안이다.
SYSTEM_PROMPT = (
    "너는 사용자가 한 문장으로 시킨 일을 할 일(Task) 동작으로 바꾸는 도우미다. "
    "사용자 메시지에 오늘 날짜(today), 끝나지 않은 할 일 목록(tasks), 사용자의 문장(text)이 있다. "
    "동작은 세 가지뿐이다. add 는 새 할 일을 만든다(title, priority, due_date). "
    "due 는 목록에 있는 할 일의 마감일을 바꾼다(id, due_date). "
    "done 은 목록에 있는 할 일을 완료로 바꾼다(id). 삭제 동작은 없다. "
    "priority 는 LOW, NORMAL, HIGH 중 하나이고 모르면 NORMAL 이다. "
    "due_date 는 YYYY-MM-DD 이며 오늘 날짜를 기준으로 '내일', '이번 주' 같은 표현을 계산한다. "
    "id 는 목록에 있는 것만 쓴다. 모든 글은 한국어로 쓴다. "
    "무엇을 하라는 말인지 알 수 없으면 actions 를 비우고 ask 에 되묻는 한 문장을 쓴다. 아니면 ask 는 null 이다. "
    'JSON 객체 하나만 답한다: {"actions": [{"kind": "add", "id": null, "title": "...", '
    '"priority": "NORMAL", "due_date": null}], "ask": null}'
)


def _action(item: dict, sent_ids: set[int]) -> dict | None:
    """동작 하나를 검사해 다섯 필드 모양으로 돌려준다. 버릴 동작이면 None."""
    kind = item.get("kind")
    if kind not in KINDS:
        return None

    if kind == "add":
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        priority = item.get("priority")
        if priority is None:
            priority = "NORMAL"
        elif priority not in PRIORITIES:
            return None
        try:
            due_date = check_due_date(item.get("due_date"))
        except ValueError:
            due_date = None  # 규칙 밖 날짜만 버리고 카드는 남긴다.
        return {"kind": "add", "id": None, "title": title.strip(),
                "priority": priority, "due_date": due_date}

    task_id = item.get("id")
    if not _is_id(task_id) or task_id not in sent_ids:
        return None
    if kind == "done":
        return {"kind": "done", "id": task_id, "title": None,
                "priority": None, "due_date": None}
    try:
        due_date = check_due_date(item.get("due_date"))
    except ValueError:
        return None
    if due_date is None:
        return None
    return {"kind": "due", "id": task_id, "title": None,
            "priority": None, "due_date": due_date}


def parse_command(text: str, sent_ids: set[int]) -> dict:
    """응답을 읽어 검증한다. 보낸 적 없는 id · 규칙 밖 동작은 버리고,
    남는 동작이 없으면 ask 를 채운다. 모양 자체가 틀리면 SuggestError(502)."""
    data = _load_object(text)
    actions, ask = data.get("actions"), data.get("ask")
    if not isinstance(actions, list) or not (ask is None or isinstance(ask, str)):
        raise SuggestError(502, FAILED)

    kept: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for item in actions:
        if not isinstance(item, dict):
            raise SuggestError(502, FAILED)
        a = _action(item, sent_ids)
        if a is None:
            continue
        if a["id"] is not None:
            key = (a["kind"], a["id"])
            if key in seen:
                continue
            seen.add(key)
        kept.append(a)

    if kept:
        return {"actions": kept, "ask": None}
    return {"actions": [], "ask": ask.strip() if ask and ask.strip() else ASK_FALLBACK}


def command(user_id: int, text: str) -> dict:
    # 할 일이 없어도 add 는 가능하므로 모델을 부른다.
    tasks = _open_tasks(user_id)
    user = json.dumps(
        {"today": date.today().isoformat(), "tasks": tasks, "text": text},
        ensure_ascii=False,
    )
    return parse_command(_ask(SYSTEM_PROMPT, user, MAX_TOKENS), {t["id"] for t in tasks})
