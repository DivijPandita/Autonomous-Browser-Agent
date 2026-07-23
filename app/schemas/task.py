from pydantic import BaseModel
from datetime import datetime


class TaskCreate(BaseModel):
    instruction: str
    start_url: str | None = None


class StepOut(BaseModel):
    step_number: int
    thought: str | None
    action_type: str
    action_payload: dict | None
    url_after: str | None
    success: bool

    class Config:
        from_attributes = True


class TaskOut(BaseModel):
    id: str
    instruction: str
    start_url: str | None
    status: str
    result: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskDetailOut(TaskOut):
    steps: list[StepOut] = []