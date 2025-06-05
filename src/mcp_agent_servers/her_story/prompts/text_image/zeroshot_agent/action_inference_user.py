PROMPT = (
    f"### Last executed action\n"
    f"{{action}}\n\n"
    f"### Current state (text)\n"
    f"{{cur_state_str}}\n\n"
    f"### Current state (image)\n"
    f"<|cur_state_image|>\n\n"
    f"### Search history\n"
    f"{{history_search}}\n"
)
