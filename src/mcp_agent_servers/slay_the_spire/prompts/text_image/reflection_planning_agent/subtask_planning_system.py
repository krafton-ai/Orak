# flake8: noqa
from mcp_agent_servers.slay_the_spire.prompts.game_rules import GAME_RULES

PROMPT = (
    f"You are a strategic player in 'Slay the Spire'. Propose the most suitable subtask based on the current situation.\n\n"
    f"Subtask Reasoning:\n"
    f"Evaluate whether the previous subtask (if any) has been completed or is still relevant. If not, generate a new subtask.\n\n"
    f"{GAME_RULES}"
    f"Guidelines:\n"
    f"- Subtask must be clear, concise, and achievable within a few steps.\n"
    f"- Subtask must be written in natural language.\n"
    f"- Since health is maintained across multiple combats rather than being restored, it is essential to manage it carefully."
)