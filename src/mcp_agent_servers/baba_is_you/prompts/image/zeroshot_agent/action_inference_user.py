# flake8: noqa

PROMPT = (
    f"Current state (image):\n"
    f"<|cur_state_image|>\n\n"
    f"Current subtask:\n"
    f"{{subtask_description}}\n\n"
    f"Last executed action:\n"
    f"{{action}}\n\n"
    f"Please respond with the following format:\n"
    f"### Reasoning\n"
    f"[Your step-by-step reasoning here]\n\n"
    f"### Actions\n"
    f"[ONLY output a sequence of actions, where each action includes a direction and number of steps only]"
)