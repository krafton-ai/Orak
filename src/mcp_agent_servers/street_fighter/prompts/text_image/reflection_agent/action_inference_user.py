# flake8: noqa

PROMPT = (
    f"### Target task\n"
    f"{{task_description}}\n\n"
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Self reflection of the last executed action\n"
    f"{{self_reflection_summary}}\n\n"
    f"### Current state (image)\n"
    f"<|cur_state_image|>\n\n"
    f"Based on the above information, analyze the current situation for what you should do for the next step. Then, you should output the exact actions you want to execute in the game.\n"
    f"You should only respond with actions from the valid action set.\n" 
    f"You should only respond in the format described below, and you should not output comments or other information.\n"
    f"Provide your response in the strict format:\n"
    f"### Reasoning\n"
    f"- ...\n"
    f"- ...\n"
    f"- ...\n"
    f"### Actions\n"
    f"- ... \n"
    f"- ... \n"
)
