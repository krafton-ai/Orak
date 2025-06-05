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

Previous game image:
<|prev_state_image|>

Current game state:
{cur_state_str}

Current game state:
<|cur_state_image|>

Relevant Memory Entries:
{relevant_memory}
"""
)