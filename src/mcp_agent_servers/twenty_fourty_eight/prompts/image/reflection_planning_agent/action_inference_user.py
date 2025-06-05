# flake8: noqa

PROMPT = (
    f"### Current subtask\n"
    f"{{subtask_description}}\n\n"
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Self reflection of the last executed action\n"
    f"{{self_reflection_summary}}\n\n"
    f"### Current state\n"
    f"<|cur_state_image|>\n\n"
    f"You should only respond in the format described below, and you should not output comments or other information.\n"
    f"Provide your response in the strict format: \n### Reasoning\n<a detailed summary of why this action was chosen>\n### Actions\n<direction>\n"
)
