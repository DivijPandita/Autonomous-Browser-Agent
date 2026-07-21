from __future__ import annotations

import json

from openai import AsyncOpenAI

from app.agent.state import AgentState
from app.agent.tools import ACTION_SCHEMA_DESCRIPTION, execute_action
from app.browser.controller import BrowserController
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = f"""You are an autonomous browser agent. You are given a task and you
control a real web browser step by step to accomplish it. At each turn you see the
current URL, a short summary of the visible text, and a numbered list of interactive
elements on the page. You choose exactly one action.

{ACTION_SCHEMA_DESCRIPTION}

Always think briefly about why you're choosing this action before committing to it.
Respond ONLY with JSON in this exact shape:
{{"thought": "<1-2 sentences>", "action": {{...one action object...}}}}
"""


async def perceive_node(state: AgentState, controller: BrowserController) -> AgentState:
    """Reads the current page: URL, trimmed visible text, and numbered interactive elements."""
    elements = await controller.get_interactive_elements()
    elements_prompt = "\n".join(e.to_prompt_line() for e in elements) or "(no interactive elements found)"

    page_text = await controller.extract_text()
    page_text_summary = page_text[:2000]  # keep the prompt bounded

    state["current_url"] = controller.current_url
    state["elements_prompt"] = elements_prompt
    state["page_text_summary"] = page_text_summary
    return state


async def plan_node(state: AgentState) -> AgentState:
    """Asks the LLM to pick the next action given the current perception + history."""
    history_lines = []
    for h in state.get("history", [])[-8:]:  # cap context growth
        history_lines.append(
            f"- step {h['step']}: thought=\"{h['thought']}\" action={h['action']} -> {h['outcome']}"
        )
    history_text = "\n".join(history_lines) or "(no actions taken yet)"

    user_prompt = f"""
TASK: {state['instruction']}

CURRENT URL: {state.get('current_url', '(not navigated yet)')}

VISIBLE PAGE TEXT (trimmed):
{state.get('page_text_summary', '')}

INTERACTIVE ELEMENTS:
{state.get('elements_prompt', '')}

HISTORY SO FAR:
{history_text}

Step {state.get('step_count', 0) + 1} of max {state.get('max_steps', settings.max_steps)}.
What is the single next action?
"""

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    state["thought"] = parsed.get("thought", "")
    state["action"] = parsed.get("action", {"type": "finish", "success": False, "summary": "LLM returned no action"})
    return state


async def act_node(state: AgentState, controller: BrowserController) -> AgentState:
    """Executes the chosen action and folds the outcome into history."""
    action = state["action"]
    outcome = await execute_action(controller, action)

    state.setdefault("history", []).append(
        {
            "step": state.get("step_count", 0) + 1,
            "thought": state.get("thought", ""),
            "action": action,
            "outcome": outcome.get("detail", ""),
        }
    )
    state["step_count"] = state.get("step_count", 0) + 1

    if action.get("type") == "finish":
        state["done"] = True
        state["result"] = action.get("summary", "")
        if not action.get("success", True):
            state["error"] = action.get("summary", "task reported as failed")

    if not outcome.get("success", True) and action.get("type") != "finish":
        # feed the failure back in - the next plan_node call will see it in history
        # and can try a different approach instead of repeating the same mistake.
        pass

    return state