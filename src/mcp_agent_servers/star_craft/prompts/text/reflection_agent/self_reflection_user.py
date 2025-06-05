
PROMPT = (
    f"### Previous state\n"
    f"{{prev_state_str}}\n\n"
    f"### Current state\n"
    f"{{cur_state_str}}\n\n"
    f"### Current subtask\n"
    f"{{subtask_description}}\n\n"
    f"### Lastley executed actions\n"
    f"{{action_executed}}\n\n"
    f"You should only respond in the format described below:\n\n"
    f"### Self_reflection\n"
    f"1. ...\n"
    f"2. ...\n"
    f"3. ...\n\n"
    f"### Self_reflection_summary\n"
    f"...\n\n"
)