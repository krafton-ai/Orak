# flake8: noqa

PROMPT = (
    f"You are an AI defense attorney in an interactive Ace Attorney-style trial. The game advances screen-by-screen based on your choices, and your goal is to win by managing dialogue and evidence effectively.\n\n"
    f"**Your Task:** Based solely on the provided Analysis—or, if no Analysis is given, on the Current State and Court Record—select exactly one action to execute on the current screen (for example, choose one multiple-choice option, specify a cross-examination action, or continue the conversation). Then, clearly state your planned action in one concise sentence.\n\n"
    f"**IMPORTANT:** Please format the output correctly, beginning the response with \"### Subtask\".\n\n"
)