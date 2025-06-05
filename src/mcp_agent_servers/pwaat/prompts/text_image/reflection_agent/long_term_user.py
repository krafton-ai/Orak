# flake8: noqa

PROMPT = (
    f"Current State (text):\n"
    f"{{cur_state_str}}\n\n"
    f"Current Screen (image screenshot):\n"
    f"<|cur_state_image|>\n\n"
    f"Last Court Record:\n"
    f"{{last_record}}\n\n"
    f"Last Decisions:\n"
    f"{{last_decisions}}\n\n"
    f"Lastest Saved Clues:\n"
    f"{{latest_saved_memory_str}}\n\n"
    f"You should only respond in the format as described below.\n"
    f"### Clue_Extraction\n"
    f"[A concise statement of a pair of (1) the contradiction if there is any, and (2) an testimony in color=#00f000 that relates to the contradiction, in a short sentence.]\n\n"
    f"### Saving\n"
    f"[**ONLY** respond with either \"Yes\" or \"No\"]"
)
