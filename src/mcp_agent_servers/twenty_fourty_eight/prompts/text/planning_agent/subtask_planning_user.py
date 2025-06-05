# flake8: noqa

PROMPT = (
    f"### Target task\n"
    f"{{task_description}}\n\n"
    f"### Previous subtask for the task\n"
    f"{{subtask_description}}\n\n"
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Previous state\n"
    f"{{prev_state_str}}\n\n"
    f"### Current state\n"
    f"{{cur_state_str}}\n\n"
    f"You MUST respond in the format described below, and you should not output comments or other information.\n"
    f"### Subtask_reasoning\n"
    f"1. ...\n"
    f"2. ...\n"
    f"3. ...\n"
    f"### Subtask\n"
    f"The current subtask is\n"
)