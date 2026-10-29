"""이번 주 계획: 끝나지 않은 할 일을 오늘부터 7일에 나눈 날짜별 목록. Claude 를 호출만 한다.

저장소는 읽기만 하고 쓰지 않는다. 모으기 · 호출 · 오류 변환은 briefing · suggest 모듈의 것을 그대로 쓴다.
"""

import json
from datetime import date, timedelta

from app.briefing import EMPTY_CHEER, _is_id, _open_tasks
from app.suggest import FAILED, SuggestError, _ask, _load_object

MAX_TOKENS = 900
DAYS = 7

# TODO(사용자 제공 필요): 프롬프트 문구는 사용자가 준 것이 아니라 임시 초안이다.
SYSTEM_PROMPT = (
    "너는 끝나지 않은 할 일을 오늘부터 7일(오늘 포함)에 나누어 배치하는 도우미다. "
    "사용자 메시지에 오늘 날짜(today)와 할 일 목록(JSON)이 있다. "
    "모든 할 일을 정확히 한 번씩, 하루에만 넣는다. "
    "마감일(due_date)이 있는 일은 마감 전날까지 끝나도록 앞쪽 날에 두고, "
    "이미 지난 일(overdue)은 오늘에 둔다. 마감일이 없는 일은 할 일이 적은 빈 날에 둔다. "
    "id 는 목록에 있는 것만 쓰고, 날짜는 YYYY-MM-DD 이며 7일 안이어야 한다. "
    "note 는 표 전체에 대한 한국어 한 문장이다. "
    'JSON 객체 하나만 답한다: {"days": [{"date": "2026-10-29", "ids": [1, 2]}], '
    '"note": "..."}'
)


def _day(v: object, first: date, last: date) -> date | None:
    """7일 안의 YYYY-MM-DD 날짜면 date, 아니면 None."""
    if not isinstance(v, str) or len(v) != 10:
        return None
    try:
        d = date.fromisoformat(v)
    except ValueError:
        return None
    return d if first <= d <= last else None


def parse_weekplan(text: str, sent_ids: set[int], today: date) -> dict:
    """응답을 읽어 검증한다. 7일 밖 날짜 · 보낸 적 없는 id · 두 날에 걸친 id 는 버리고,
    남는 날이 없으면 SuggestError(502). 모양 자체가 틀리면 502."""
    data = _load_object(text)
    days, note = data.get("days"), data.get("note")
    if not isinstance(days, list) or not isinstance(note, str):
        raise SuggestError(502, FAILED)

    first, last = today, today + timedelta(days=DAYS - 1)
    by_date: dict[date, list[int]] = {}
    seen: set[int] = set()
    for entry in days:
        if not isinstance(entry, dict) or not isinstance(entry.get("ids"), list):
            raise SuggestError(502, FAILED)
        d = _day(entry.get("date"), first, last)
        if d is None:
            continue
        for i in entry["ids"]:
            if _is_id(i) and i in sent_ids and i not in seen:
                seen.add(i)
                by_date.setdefault(d, []).append(i)
    if not by_date:
        raise SuggestError(502, FAILED)
    return {
        "days": [{"date": d.isoformat(), "ids": ids} for d, ids in sorted(by_date.items())],
        "note": note,
    }


def weekplan(user_id: int) -> dict:
    tasks = _open_tasks(user_id)
    if not tasks:
        return {"days": [], "note": EMPTY_CHEER}
    today = date.today()
    user = json.dumps({"today": today.isoformat(), "tasks": tasks}, ensure_ascii=False)
    text = _ask(SYSTEM_PROMPT, user, MAX_TOKENS)
    return parse_weekplan(text, {t["id"] for t in tasks}, today)
