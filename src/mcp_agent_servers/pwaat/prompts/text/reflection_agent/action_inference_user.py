# flake8: noqa

PROMPT = (
    f"Current State:\n"
    f"{{cur_state_str}}\n\n"
    f"Last Court Record:\n"
    f"{{last_record}}\n\n"
    f"Last Decisions:\n"
    f"{{last_decisions}}\n\n"
    f"Analysis:\n"
    f"{{analysis}}\n\n"
    f"Planned Subtask:\n"
    f"{{subtask_description}}\n\n"
    f"Retrieved Long Term Memory:\n"
    f"{{retrieved_memory_str}}\n\n"
    f"{{possible_options}}\n\n"
    f"Please respond using the following format:\n"
    f"### Reasoning\n"
    f"[Your step-by-step reasoning here.]\n\n"
    f"### Actions\n"
    f"[**ONLY** output the **INTEGER** number corresponding to the correct option from the **Possible Options**.]"
)
