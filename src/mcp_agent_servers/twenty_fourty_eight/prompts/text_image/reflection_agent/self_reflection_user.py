# flake8: noqa

PROMPT = (
    f"### Target task\n"
    f"{{task_description}}\n\n"
    f"### Previous state (text)\n"
    f"{{prev_state_str}}\n\n"
    f"### Previous state (image)\n"
    f"<|prev_state_image|>\n\n"
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Current state (text)\n"
    f"{{cur_state_str}}\n\n"
    f"### Current state (image)\n"
    f"<|cur_state_image|>\n\n"
    f"You should only respond in the format as described below.\n"
    f"### Self_reflection\n"
    f"1. ...\n"
    f"2. ...\n"
    f"3. ...\n"
    f"### Self_reflection_summary\n"
    f"..."
)