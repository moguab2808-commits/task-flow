import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

Status = Literal["TODO", "IN_PROGRESS", "DONE"]
Priority = Literal["LOW", "NORMAL", "HIGH"]

PRIORITIES = ("LOW", "NORMAL", "HIGH")
_DATE_FORMAT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def check_priority(v: object) -> str:
    """우선순위는 세 값 중 하나다. 비울 수 없다 (null 은 거절)."""
    if v is None:
        raise ValueError("우선순위는 비울 수 없습니다. LOW, NORMAL, HIGH 중 하나를 골라 주세요.")
    if v not in PRIORITIES:
        raise ValueError("우선순위는 LOW, NORMAL, HIGH 중 하나여야 합니다.")
    return v  # type: ignore[return-value]


def check_due_date(v: object) -> str | None:
    """마감일은 YYYY-MM-DD 날짜만이다. null 은 '마감일 없음'이다. 지난 날짜도 허용한다."""
    if v is None:
        return None
    if not isinstance(v, str) or not _DATE_FORMAT.fullmatch(v):
        raise ValueError("마감일은 YYYY-MM-DD 형식의 날짜여야 합니다.")
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ValueError("존재하지 않는 날짜입니다. 마감일을 확인해 주세요.") from None
    return v


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""
    priority: Priority = "NORMAL"
    due_date: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("제목을 입력해 주세요.")
        return v

    @field_validator("priority", mode="before")
    @classmethod
    def priority_valid(cls, v: object) -> str:
        return check_priority(v)

    @field_validator("due_date", mode="before")
    @classmethod
    def due_date_valid(cls, v: object) -> str | None:
        return check_due_date(v)


class SignupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("사용자 이름을 입력해 주세요.")
        if len(v) > 50:
            raise ValueError("사용자 이름은 50자 이하로 입력해 주세요.")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if not v:
            raise ValueError("비밀번호를 입력해 주세요.")
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        if len(v) > 128:
            raise ValueError("비밀번호는 128자 이하로 입력해 주세요.")
        return v


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_present(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("사용자 이름을 입력해 주세요.")
        return v

    @field_validator("password")
    @classmethod
    def password_present(cls, v: str) -> str:
        if not v:
            raise ValueError("비밀번호를 입력해 주세요.")
        return v


class UserOut(BaseModel):
    username: str


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    status: Status
    created_at: str
    updated_at: str
    priority: Priority
    due_date: str | None
    is_overdue: bool


class SuggestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("제목을 입력해 주세요.")
        return v


class SuggestOut(BaseModel):
    priority: Priority
    due_date: str | None
    reason: str


class SuggestOptionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("제목을 입력해 주세요.")
        return v


class OptionOut(BaseModel):
    title: str
    description: str
    priority: Priority
    due_date: str | None


class SuggestOptionsOut(BaseModel):
    items: list[OptionOut]


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status


class ContentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    # 보내지 않으면 그대로 둔다. priority 는 null 을 거절하고, due_date 는 null 이면 지운다.
    # "보내지 않음"과 null 은 model_fields_set 으로 구별한다.
    priority: Priority | None = None
    due_date: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("제목을 입력해 주세요.")
        return v

    @field_validator("priority", mode="before")
    @classmethod
    def priority_valid(cls, v: object) -> str:
        return check_priority(v)

    @field_validator("due_date", mode="before")
    @classmethod
    def due_date_valid(cls, v: object) -> str | None:
        return check_due_date(v)


class BriefingPick(BaseModel):
    id: int
    reason: str


class BriefingOut(BaseModel):
    top3: list[BriefingPick]
    later: list[int]
    cheer: str


class WeekDay(BaseModel):
    date: str
    ids: list[int]


class WeekplanOut(BaseModel):
    days: list[WeekDay]
    note: str
