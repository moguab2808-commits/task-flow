"""Task 의 우선순위 · 마감일 제안과 할 일 후보 제안. Claude 를 호출만 하고 DB 는 건드리지 않는다.

이 모듈은 repository · db 를 가져오지 않는다. 어떤 경우에도 저장소를 바꾸지 않는다.
"""

import json
import random
import re
from datetime import date

import anthropic

from app.config import anthropic_api_key
from app.schemas import PRIORITIES, check_due_date

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 300
OPTIONS_MAX_TOKENS = 900
TIMEOUT_SECONDS = 20.0
OPTIONS_MIN, OPTIONS_MAX = 3, 5

# TODO(사용자 제공 필요): 아래 프롬프트 문구는 사용자가 준 것이 아니라 임시 초안이다.
# 확정 문구를 받으면 그대로 바꾼다. 바꿀 곳은 이 네 상수뿐이다.
SYSTEM_PROMPT = (
    "너는 할 일(Task)의 우선순위와 마감일을 제안하는 도우미다. "
    "priority 는 LOW, NORMAL, HIGH 중 하나이고 확신이 없으면 NORMAL 이다. "
    "due_date 는 YYYY-MM-DD 형식의 날짜이거나, 알 수 없으면 null 이다. "
    "오늘 날짜를 기준으로 '내일', '이번 주' 같은 표현을 계산한다. "
    'JSON 객체 하나만 답한다: {"priority": ..., "due_date": ..., "reason": "한 문장"}'
)
USER_TEMPLATE = "Title: {title}\ndescription: {description}\n오늘 날짜: {today}"

OPTIONS_SYSTEM_PROMPT = (
    "너는 사용자가 적은 주제 한 줄을 할 일(Task) 여러 개로 나누는 도우미다. "
    "할 일의 개수는 사용자 메시지에 적힌 개수와 정확히 같아야 한다. "
    "각 할 일은 title(짧은 제목), description(한두 문장), priority, due_date 를 가진다. "
    "priority 는 LOW, NORMAL, HIGH 중 하나이고 due_date 는 YYYY-MM-DD 이거나 null 이다. "
    "오늘 날짜를 기준으로 '내일', '이번 주' 같은 표현을 계산한다. "
    'JSON 객체 하나만 답한다: {"items": [{"title": ..., "description": ..., '
    '"priority": ..., "due_date": ...}]}'
)
OPTIONS_USER_TEMPLATE = "주제: {title}\n할 일 개수: {count}개\n오늘 날짜: {today}"

KEY_OFF = "AI 기능 꺼짐"
BUSY = "AI 가 지금 바쁩니다. 잠시 뒤 다시 시도해 주세요."
FAILED = "제안 실패"


class SuggestError(Exception):
    """라우터가 status_code · detail 그대로 응답으로 바꾸는 오류."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


_FENCE = re.compile(r"^(?:'''|```)[a-zA-Z]*\s*(.*?)\s*(?:'''|```)$", re.DOTALL)


def _strip_fence(text: str) -> str:
    text = text.strip()
    m = _FENCE.match(text)
    return m.group(1).strip() if m else text


def _load_object(text: str) -> dict:
    try:
        data = json.loads(_strip_fence(text))
    except ValueError:
        raise SuggestError(502, FAILED) from None
    if not isinstance(data, dict):
        raise SuggestError(502, FAILED)
    return data


def _priority_and_due(data: dict) -> tuple[str, str | None]:
    # priority 가 없으면 기본값 NORMAL, 값이 있는데 허용 밖이면 거절한다.
    priority = data.get("priority", "NORMAL")
    if priority not in PRIORITIES:
        raise SuggestError(502, FAILED)
    try:
        return priority, check_due_date(data.get("due_date"))
    except ValueError:
        raise SuggestError(502, FAILED) from None


def parse_suggestion(text: str) -> dict:
    """응답 문자열을 읽어 검증한다. 허용 밖이면 SuggestError(502)."""
    data = _load_object(text)
    priority, due_date = _priority_and_due(data)
    reason = data.get("reason", "")
    if not isinstance(reason, str):
        raise SuggestError(502, FAILED)
    return {"priority": priority, "due_date": due_date, "reason": reason}


def parse_options(text: str) -> dict:
    """할 일 후보 3~5개를 검증한다. 하나라도 모양이 다르면 SuggestError(502)."""
    items = _load_object(text).get("items")
    if not isinstance(items, list) or not OPTIONS_MIN <= len(items) <= OPTIONS_MAX:
        raise SuggestError(502, FAILED)
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise SuggestError(502, FAILED)
        title = item.get("title")
        description = item.get("description", "")
        if not isinstance(title, str) or not title.strip() or not isinstance(description, str):
            raise SuggestError(502, FAILED)
        priority, due_date = _priority_and_due(item)
        out.append(
            {"title": title.strip(), "description": description,
             "priority": priority, "due_date": due_date}
        )
    return {"items": out}


def _ask(system: str, user: str, max_tokens: int) -> str:
    """Claude 를 한 번 부르고 답 문자열을 돌려준다. 실패는 SuggestError 로 바꾼다."""
    api_key = anthropic_api_key()
    if api_key is None:
        raise SuggestError(503, KEY_OFF)

    client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        raise SuggestError(503, KEY_OFF) from None
    except (
        anthropic.RateLimitError,
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
    ):
        raise SuggestError(503, BUSY) from None
    except anthropic.APIStatusError as e:
        # 529 overloaded 와 5xx 는 바쁨. 그 밖의 오류(요청 형식 등)는 제안 실패다.
        if e.status_code >= 500:
            raise SuggestError(503, BUSY) from None
        raise SuggestError(502, FAILED) from None

    # 잘린 답과 거절은 제안 실패다.
    if response.stop_reason in ("max_tokens", "refusal"):
        raise SuggestError(502, FAILED)
    return "".join(b.text for b in response.content if b.type == "text")


def suggest(title: str, description: str) -> dict:
    user = USER_TEMPLATE.format(
        title=title, description=description, today=date.today().isoformat()
    )
    return parse_suggestion(_ask(SYSTEM_PROMPT, user, MAX_TOKENS))


def suggest_options(title: str) -> dict:
    # 개수는 서버가 3~5 중에서 무작위로 정한다. 그대로 두면 모델이 늘 같은 개수를 고른다.
    count = random.randint(OPTIONS_MIN, OPTIONS_MAX)
    user = OPTIONS_USER_TEMPLATE.format(
        title=title, count=count, today=date.today().isoformat()
    )
    return parse_options(_ask(OPTIONS_SYSTEM_PROMPT, user, OPTIONS_MAX_TOKENS))
