"""
Defines the fixed set of actions the LLM is allowed to choose from, and
executes them against a BrowserController. Keeping this a closed set (rather
than letting the LLM write arbitrary Playwright code) is what keeps the agent
safe and debuggable.
"""

from __future__ import annotations

from typing import Any

from app.browser.controller import BrowserController

ACTION_SCHEMA_DESCRIPTION = """
You must respond with a single JSON object describing exactly one action.
Allowed actions:

{"type": "navigate", "url": "<full url>"}
{"type": "click", "target": <element index>}
{"type": "type", "target": <element index>, "text": "<text to enter>", "submit": <true|false>}
{"type": "scroll", "direction": "down" | "up"}
{"type": "extract", "target": <element index or null for whole page>, "label": "<short name for this data>"}
{"type": "wait", "ms": <milliseconds>}
{"type": "finish", "success": <true|false>, "summary": "<final answer / what was accomplished>"}

Rules:
- Only ever output ONE action per turn.
- Use "finish" as soon as the task's goal is satisfied, or if it becomes impossible - don't keep clicking around aimlessly.
- Prefer "extract" to pull out the actual data (prices, search results, confirmation numbers) before finishing, so the summary is grounded in real page content.
- Element indices come from the numbered [i] list you're given - never invent one.
"""


async def execute_action(controller: BrowserController, action: dict[str, Any]) -> dict[str, Any]:
    """Runs `action` against the live browser. Returns an outcome dict that gets
    folded back into agent state / history."""
    action_type = action.get("type")

    try:
        if action_type == "navigate":
            await controller.goto(action["url"])
            return {"success": True, "detail": f"navigated to {action['url']}"}

        if action_type == "click":
            await controller.click(int(action["target"]))
            return {"success": True, "detail": f"clicked element {action['target']}"}

        if action_type == "type":
            await controller.type_text(int(action["target"]), action["text"])
            if action.get("submit"):
                await controller.press_key("Enter")
            return {"success": True, "detail": f"typed into element {action['target']}"}

        if action_type == "scroll":
            await controller.scroll(action.get("direction", "down"))
            return {"success": True, "detail": f"scrolled {action.get('direction', 'down')}"}

        if action_type == "extract":
            target = action.get("target")
            text = await controller.extract_text(int(target) if target is not None else None)
            return {"success": True, "detail": "extracted text", "data": text, "label": action.get("label", "data")}

        if action_type == "wait":
            import asyncio
            await asyncio.sleep(min(action.get("ms", 1000), 10000) / 1000)
            return {"success": True, "detail": "waited"}

        if action_type == "finish":
            return {"success": True, "detail": "finished", "final": True}

        return {"success": False, "detail": f"unknown action type: {action_type}"}

    except Exception as exc:  # noqa: BLE001 - we want to feed the error back to the LLM, not crash the graph
        return {"success": False, "detail": f"action failed: {exc}"}