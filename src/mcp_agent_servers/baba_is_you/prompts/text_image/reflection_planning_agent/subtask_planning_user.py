# flake8: noqa

PROMPT = (
    f"Here is the current game state information to help you plan the next subtask.\n\n"
    f"Previous proposed subtask:\n"
    f"{{subtask_description}}\n\n"
    f"Last executed action:\n"
    f"{{action}}\n\n"
    f"Result of the last executed action:\n"
    f"{{self_reflection}}\n\n"
    f"Current state (text):\n"
    f"{{cur_state_str}}\n\n"
    f"Current state (image):\n"
    f"<|cur_state_image|>\n\n"
    f"You MUST respond in the format described below:\n"
    f"### Subtask_reasoning\n"
    f"1. ...\n"
    f"2. ...\n"
    f"3. ...\n"
    f"4. ...\n"
    f"### Subtask\n"
    f"..."
) 