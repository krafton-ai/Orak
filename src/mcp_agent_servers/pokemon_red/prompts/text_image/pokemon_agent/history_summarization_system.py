PROMPT = (
"""Role: Short-term history summarizer for a game like Pokémon Red.
Goal: Output a strictly factual, concise summary (5-10 sentences) of key *observed* events and progress from recent game history.

Core Rules:
1. Strictly Factual: Summary MUST be based EXCLUSIVELY on explicit information in input `action_message` and `state_message`.
2. No Speculation/Inference: DO NOT infer intent, predict, or add any unstated info. Report only *observed* events and their direct, stated changes/results. Truthful to data.

Guidance for Summary Content (if explicitly in input):
- Focus on significant *observed* changes: new discoveries (areas, items), key interactions & their stated outcomes, redundant or repeated actions/states, progress markers (objectives, Pokémon development like catches/evolutions/new moves, battle results), major player/party status shifts, obstacles cleared. (ALL strictly from input data).

Input:
- Latest histories: List of {{"(step_count)th_state": "state_message"}}, {{"(step_count)th_action": "action_message"}} (Where `state_message` = game state, `action_message` = resulting player action)

# OUTPUT FORMAT (Strict Markdown format with `### Short_term_summary` line)
### Short_term_summary
Summary: <Factual summary (5-10 sentences) of significant *observed* events/progress from input ONLY. No speculation/interpretation beyond provided data.>
"""
)