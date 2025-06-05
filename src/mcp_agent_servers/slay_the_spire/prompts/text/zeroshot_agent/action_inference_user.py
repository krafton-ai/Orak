# flake8: noqa

PROMPT = (
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Current state\n"
    f"{{cur_state_str}}\n\n"
    f"You should only respond in the format described below, and you should not output comments or other information.\n"
    f"### Reasoning\n"
    f"...\n"
    f"### Actions\n"
    f"..."
)