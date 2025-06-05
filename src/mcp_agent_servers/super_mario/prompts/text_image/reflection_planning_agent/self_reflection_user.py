PROMPT = (
"""### Past Game State (text)
{prev_state_str}

### Past Game State (image)
<|prev_state_image|>

### Past Mario Action
{past_mario_action}

### Current Game State (text)
{cur_state_str}

### Current Game State (image)
<|cur_state_image|>
"""
)