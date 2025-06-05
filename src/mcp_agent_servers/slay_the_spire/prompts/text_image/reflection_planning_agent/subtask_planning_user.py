# flake8: noqa

PROMPT = (
    f"### Target task\n"
    f"{{task_description}}\n\n"
    f"### Previous subtask for the task\n"
    f"{{subtask_description}}\n\n"
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Self reflection of the last executed action\n"
    f"{{self_reflection_summary}}\n\n"
    f"### Current state (text)\n"
    f"{{cur_state_str}}\n\n"
    f"### Current state (image)\n"
    f"<|cur_state_image|>\n\n"
    f"You MUST respond in the format described below, and you should not output comments or other information.\n"
    f"### Subtask_reasoning\n"
    f"...\n"
    f"### Subtask\n"
    f"..."
)