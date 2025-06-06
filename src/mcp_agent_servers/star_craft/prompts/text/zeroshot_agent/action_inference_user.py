PROMPT = (
    f"### Current state\n"
    f"{{cur_state_str}}\n\n"
    f"You should only respond in the format described below:\n\n"
    f"### Analysis\n"
    f"1. ...\n"
    f"2. ...\n"
    f"3. ...\n"
    f"...\n\n"
    f"### Reasoning\n"
    f"1: [Current Resource] [ACTION] [Cost] [Availability] [Updated Resource]\n"
    f"2: ...\n"
    f"3: ...\n"
    f"...\n\n"
    f"### Actions\n"
    f"1: <ACTION1>\n"
    f"2: <ACTION2>\n"
    f"3: <ACTION3>\n"
    f"...\n\n"
)
