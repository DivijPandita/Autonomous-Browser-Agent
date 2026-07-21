import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Task(Base):
    """A single high-level instruction given to the agent, e.g.
    'Go to indeed.com and find 5 SWE internships in Bangalore posted this week.'
    """
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    start_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending/running/success/failed
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    steps: Mapped[list["Step"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Step(Base):
    """One perceive -> plan -> act cycle taken by the agent while executing a Task."""
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    step_number: Mapped[int] = mapped_column(Integer)
    thought: Mapped[str | None] = mapped_column(Text, nullable=True)      # LLM's reasoning
    action_type: Mapped[str] = mapped_column(String)                     # navigate/click/type/extract/finish...
    action_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    url_before: Mapped[str | None] = mapped_column(String, nullable=True)
    url_after: Mapped[str | None] = mapped_column(String, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="steps")


class ExtractedData(Base):
    """Structured data the agent pulled off pages (search results, prices, form
    confirmations, etc.) so it survives independently of the raw step log."""
    __tablename__ = "extracted_data"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    label: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)