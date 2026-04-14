from enum import Enum
from typing import Generic, TypeVar
from datetime import datetime, timezone
from pydantic import BaseModel, Field

T = TypeVar("T")


class PipelineStatus(str, Enum):
    PENDING = "pending"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    BUILDING_FIG = "building_fig"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskResult(BaseModel, Generic[T]):
    status: str
    data: T | None = None
    error: str | None = None
    duration_ms: int = 0


class PipelineState(BaseModel):
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    url: str
    status: PipelineStatus = PipelineStatus.PENDING
    collector_output: dict | None = None
    analyst_output: dict | None = None
    fig_output: dict | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)