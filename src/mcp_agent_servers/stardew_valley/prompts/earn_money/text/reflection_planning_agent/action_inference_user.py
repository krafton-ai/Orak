# flake8: noqa

PROMPT = (
    f"### Current subtask\n"
    f"{{subtask_description}}\n\n"
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Self reflection of the last executed action\n"
    f"{{self_reflection_summary}}\n\n"
    f"### Current state\n"
    f"{{cur_state_str}}\n\n"
    f"You should only respond in the format described below, and you should not output comments or other information.\n"
    f"### Reasoning\n"
    f"1. ...\n"
    f"2. ...\n"
    f"3. ...\n"
    f"### Actions\n"
    f"```python\n"
    f"action(args1=x,args2=y)\n"
    f"```"
)