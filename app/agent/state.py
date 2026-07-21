from typing import TypedDict, Optional, Any


class AgentState(TypedDict, total=False):
    task_id: str
    instruction: str          # the human's goal, e.g. "book a table for 2 at 8pm on OpenTable"
    start_url: Optional[str]

    current_url: str
    elements_prompt: str      # numbered list of interactive elements, rendered for the LLM
    page_text_summary: str    # trimmed visible text, gives the LLM page context

    thought: str               # LLM's reasoning for this step
    action: dict[str, Any]     # the parsed next action, e.g. {"type": "click", "target": 3}

    history: list[dict]        # log of past (thought, action, outcome) for the prompt + DB
    step_count: int
    max_steps: int

    done: bool
    result: Optional[str]
    error: Optional[str]