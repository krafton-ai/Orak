# subtask_planning_user prompt

PROMPT = (
"""Recent history:
{short_term_summary}

Self-Reflection:
{self_reflection}

Current game state:
{cur_state_str}

Current game state:
<|cur_state_image|>

Relevant memory entries:
{relevant_memory}
"""
)
