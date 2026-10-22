from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

Status = Literal["TODO", "IN_PROGRESS", "DONE"]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("제목을 입력해 주세요.")
        return v


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


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status


class ContentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("제목을 입력해 주세요.")
        return v
