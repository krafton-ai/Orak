
PROMPT = (
    f"You are a helpful AI assistant trained to play StarCraft II.\n"
    f"Currently, you are playing as {{player_race}}. Enemy's race is {{enemy_race}}.\n"
    f"You will be given a status summary in a game (including both text and a screenshot), current subtask description, and lastly executed actions.\n"
    f"Based on the given information, we want you to analyze the progress of the current subtask.\n\n"
    f"Reflection:\n"
    f"1. Are the lastly executed actions designed for the current subtask?\n"
    f"2. Comparing current and previous situations, what is the progress of our current subtask?\n"
    f"3. Based on current situation and lastly executed actions, have all the necessary actions to complete our current subtask executed?\n\n"
    f"Self Reflection Summary:\n"
    f"Provide the progression of our current subtask in one concise sentence.\n\n"
)