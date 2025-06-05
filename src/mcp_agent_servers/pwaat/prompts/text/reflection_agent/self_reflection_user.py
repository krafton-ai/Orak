# flake8: noqa

PROMPT = (
    f"Current State:\n"
    f"{{cur_state_str}}\n\n"
    f"Last Court Record:\n"
    f"{{last_record}}\n\n"
    f"Last Decisions:\n"
    f"{{last_decisions}}\n\n"
    f"Last Analysis:\n"
    f"{{analysis}}\n\n"
    f"You should only respond in the format as described below.\n"
    f"### Reasoning\n"
    f"[Your step-by-step reasoning here.]\n\n"
    f"### Analysis\n"
    f"[A concise, precise summary of the above reasoning in a few short sentences.]"
)
