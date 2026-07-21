from __future__ import annotations

from functools import partial

from langgraph.graph import StateGraph, END

from app.agent.nodes import perceive_node, plan_node, act_node
from app.agent.state import AgentState
from app.browser.controller import BrowserController
from app.core.config import settings


def route_after_act(state: AgentState) -> str:
    if state.get("done"):
        return END
    if state.get("step_count", 0) >= state.get("max_steps", settings.max_steps):
        state["done"] = True
        state["error"] = state.get("error") or "max_steps reached without finishing"
        return END
    return "perceive"


def build_graph(controller: BrowserController):
    graph = StateGraph(AgentState)

    graph.add_node("perceive", partial(perceive_node, controller=controller))
    graph.add_node("plan", plan_node)
    graph.add_node("act", partial(act_node, controller=controller))

    graph.set_entry_point("perceive")
    graph.add_edge("perceive", "plan")
    graph.add_edge("plan", "act")
    graph.add_conditional_edges("act", route_after_act, {"perceive": "perceive", END: END})

    return graph.compile()


async def run_agent(instruction: str, start_url: str | None, task_id: str) -> AgentState:
    controller = BrowserController()
    await controller.start()

    try:
        if start_url:
            await controller.goto(start_url)

        initial_state: AgentState = {
            "task_id": task_id,
            "instruction": instruction,
            "start_url": start_url,
            "history": [],
            "step_count": 0,
            "max_steps": settings.max_steps,
            "done": False,
        }

        app = build_graph(controller)
        final_state = await app.ainvoke(initial_state)
        return final_state
    finally:
        await controller.close()