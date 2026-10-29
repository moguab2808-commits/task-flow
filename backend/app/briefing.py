"""오늘 브리핑: 끝나지 않은 할 일 중 먼저 할 일 셋, 미뤄도 되는 일, 응원 한 문장. Claude 를 호출만 한다.

저장소는 읽기만 하고 쓰지 않는다. 호출과 오류 변환은 suggest 모듈의 것을 그대로 쓴다.
"""

import json
from datetime import date

from app import repository
from app.suggest import FAILED, SuggestError, _ask, _load_object

MAX_TOKENS = 600
TOP_MAX = 3
EMPTY_CHEER = "오늘은 비어 있어요"

# TODO(사용자 제공 필요): 프롬프트 문구는 사용자가 준 것이 아니라 임시 초안이다.
SYSTEM_PROMPT = (
    "너는 오늘 할 일을 골라 주는 도우미다. 사용자 메시지에 끝나지 않은 할 일 목록(JSON)이 있다. "
    "top3 는 오늘 먼저 할 일 최대 3개로 각각 id 와 reason(한 문장 이유)을 가진다. "
    "later 는 미뤄도 되는 할 일의 id 목록이다. cheer 는 응원 한 문장이다. "
    "id 는 목록에 있는 것만 쓴다. 모든 글은 한국어로 쓴다. "
    'JSON 객체 하나만 답한다: {"top3": [{"id": 1, "reason": "..."}], '
    '"later": [2, 3], "cheer": "..."}'
)


def _open_tasks(user_id: int) -> list[dict]:
    # 설명은 모델에 보내지 않는다. 필요한 다섯 값만 뽑는다.
    return [
        {
            "id": t["id"],
            "title": t["title"],
            "priority": t["priority"],
            "due_date": t["due_date"],
            "overdue": t["is_overdue"],
        }
        for t in repository.list_tasks(user_id)
        if t["status"] != "DONE"
    ]


def _is_id(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def parse_briefing(text: str, sent_ids: set[int]) -> dict:
    """응답을 읽어 검증한다. 보낸 적 없는 id 는 버리고 top3 는 셋까지. 형식 위반은 502."""
    data = _load_object(text)
    top3, later, cheer = data.get("top3"), data.get("later"), data.get("cheer")
    if not isinstance(top3, list) or not isinstance(later, list) or not isinstance(cheer, str):
        raise SuggestError(502, FAILED)

    picks: list[dict] = []
    for p in top3:
        if not isinstance(p, dict) or not _is_id(p.get("id")) or not isinstance(p.get("reason"), str):
            raise SuggestError(502, FAILED)
        if p["id"] in sent_ids and all(p["id"] != q["id"] for q in picks):
            picks.append({"id": p["id"], "reason": p["reason"]})
    picks = picks[:TOP_MAX]
    if not picks:
        raise SuggestError(502, FAILED)

    picked = {p["id"] for p in picks}
    rest: list[int] = []
    for i in later:
        if not _is_id(i):
            raise SuggestError(502, FAILED)
        if i in sent_ids and i not in picked and i not in rest:
            rest.append(i)
    return {"top3": picks, "later": rest, "cheer": cheer}


def briefing(user_id: int) -> dict:
    tasks = _open_tasks(user_id)
    if not tasks:
        return {"top3": [], "later": [], "cheer": EMPTY_CHEER}
    user = json.dumps(
        {"today": date.today().isoformat(), "tasks": tasks}, ensure_ascii=False
    )
    text = _ask(SYSTEM_PROMPT, user, MAX_TOKENS)
    return parse_briefing(text, {t["id"] for t in tasks})
