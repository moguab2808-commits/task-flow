"""Task 의 우선순위 · 마감일 제안. Claude 를 호출만 하고 DB 는 건드리지 않는다.

이 모듈은 repository · db 를 가져오지 않는다. 어떤 경우에도 저장소를 바꾸지 않는다.
"""

import json
import re
from datetime import date

import anthropic

from app.config import anthropic_api_key
from app.schemas import PRIORITIES, check_due_date

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 300
TIMEOUT_SECONDS = 20.0

# TODO(사용자 제공 필요): 아래 두 값은 사용자가 준 문구가 아니라 임시 초안이다.
# 사용자가 역할 지시문과 메시지 틀을 주면 그대로 바꾼다. 바꿀 곳은 이 두 상수뿐이다.
SYSTEM_PROMPT = (
    "너는 할 일(Task)의 우선순위와 마감일을 제안하는 도우미다. "
    "priority 는 LOW, NORMAL, HIGH 중 하나이고 확신이 없으면 NORMAL 이다. "
    "due_date 는 YYYY-MM-DD 형식의 날짜이거나, 알 수 없으면 null 이다. "
    "오늘 날짜를 기준으로 '내일', '이번 주' 같은 표현을 계산한다. "
    'JSON 객체 하나만 답한다: {"priority": ..., "due_date": ..., "reason": "한 문장"}'
)
USER_TEMPLATE = "Title: {title}\ndescription: {description}\n오늘 날짜: {today}"

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


def parse_suggestion(text: str) -> dict:
    """응답 문자열을 읽어 검증한다. 허용 밖이면 SuggestError(502)."""
    try:
        data = json.loads(_strip_fence(text))
    except ValueError:
        raise SuggestError(502, FAILED) from None
    if not isinstance(data, dict):
        raise SuggestError(502, FAILED)

    priority = data.get("priority", "NORMAL")
    if priority not in PRIORITIES:
        raise SuggestError(502, FAILED)
    try:
        due_date = check_due_date(data.get("due_date"))
    except ValueError:
        raise SuggestError(502, FAILED) from None
    reason = data.get("reason", "")
    if not isinstance(reason, str):
        raise SuggestError(502, FAILED)
    return {"priority": priority, "due_date": due_date, "reason": reason}


def suggest(title: str, description: str) -> dict:
    api_key = anthropic_api_key()
    if api_key is None:
        raise SuggestError(503, KEY_OFF)

    client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "disabled"},
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": USER_TEMPLATE.format(
                        title=title,
                        description=description,
                        today=date.today().isoformat(),
                    ),
                }
            ],
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
    text = "".join(b.text for b in response.content if b.type == "text")
    return parse_suggestion(text)
