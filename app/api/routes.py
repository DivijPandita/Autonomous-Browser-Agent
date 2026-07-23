from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_agent
from app.db.models import Task, Step
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.task import TaskCreate, TaskOut, TaskDetailOut

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _execute_and_persist(task_id: str, instruction: str, start_url: str | None) -> None:
    """Runs in the background so the POST /tasks call returns immediately."""
    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        task.status = "running"
        await db.commit()

    try:
        final_state = await run_agent(instruction, start_url, task_id)

        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            task.status = "success" if not final_state.get("error") else "failed"
            task.result = final_state.get("result")
            task.error = final_state.get("error")
            await db.commit()

            for h in final_state.get("history", []):
                db.add(
                    Step(
                        task_id=task_id,
                        step_number=h["step"],
                        thought=h["thought"],
                        action_type=h["action"].get("type", "unknown"),
                        action_payload=h["action"],
                        url_after=None,
                        success="failed" not in h["outcome"],
                    )
                )
            await db.commit()

    except Exception as exc:  # noqa: BLE001
        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            task.status = "failed"
            task.error = str(exc)
            await db.commit()


@router.post("", response_model=TaskOut)
async def create_task(payload: TaskCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    task = Task(id=str(uuid.uuid4()), instruction=payload.instruction, start_url=payload.start_url, status="pending")
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(_execute_and_persist, task.id, task.instruction, task.start_url)
    return task


@router.get("/{task_id}", response_model=TaskDetailOut)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    result = await db.execute(select(Step).where(Step.task_id == task_id).order_by(Step.step_number))
    steps = result.scalars().all()
    task_out = TaskDetailOut.model_validate(task)
    task_out.steps = [s for s in steps]
    return task_out


@router.get("", response_model=list[TaskOut])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).order_by(Task.created_at.desc()))
    return result.scalars().all()