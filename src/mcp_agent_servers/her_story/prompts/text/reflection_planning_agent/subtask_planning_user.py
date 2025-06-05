PROMPT = (
    f"### Current subtask\n"
    f"{{subtask_description}}\n\n"
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Self reflection of the last executed action\n"
    f"{{self_reflection_summary}}\n\n"
    f"### Current state\n"
    f"{{cur_state_str}}\n\n"
    f"### Search history\n"
    f"{{history_search}}\n"
)
