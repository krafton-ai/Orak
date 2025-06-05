# action_inference_user prompt

PROMPT = (
"""
Recent History:
{short_term_summary}

Current State:
{cur_state_str}

Recent Critique:
{self_reflection}

Next Subtask:
{subtask_description}

Relevant Memory Entries:
{relevant_memory}
"""
)