# flake8: noqa

PROMPT = (
    f"### Last Executed Action\n"
    f"{{action}}\n\n"
    f"### Current State\n"
    f"{{cur_state_str}}\n\n"
    f"You should only respond in the format described below.\n\n"
    f"### Reasoning\n"
    f"1. ...\n"
    f"2. ...\n"
    f"3. ...\n\n"
    f"### Actions\n"
    f"...\n"
)