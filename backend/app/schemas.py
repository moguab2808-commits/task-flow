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


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    status: Status
    created_at: str
    updated_at: str
