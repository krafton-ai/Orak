# self_reflection_user prompt

PROMPT = (
"""Recent history:
{short_term_summary}

Current subtask:
{subtask}

Subtask reasoning:
{subtask_reasoning}

Previous game state:
{prev_state_str}

Current game state:
{cur_state_str}

Relevant Memory Entries:
{relevant_memory}
"""
)