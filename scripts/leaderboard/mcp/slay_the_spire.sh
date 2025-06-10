# LLMs
# "gpt-4o-mini" "gpt-4o" "o3-mini" "claude-3-7-sonnet-20250219" "gemini-2.5-pro-preview-03-25" "deepseek-reasoner"
# SLMs
# "meta-llama/Llama-3.2-1B-Instruct" "meta-llama/Llama-3.2-3B-Instruct" "Qwen/Qwen2.5-3B-Instruct" "Qwen/Qwen2.5-7B-Instruct" "nvidia/Nemotron-Mini-4B-Instruct" "nvidia/Mistral-NeMo-Minitron-8B-Instruct"

game="slay_the_spire"
model="gpt-4o-mini"
agent="reflection_planning_agent"
input_modality="text"  # (text, image, text_image)

uv run ./scripts/mcp_play_game.py \
    --config="./src/mcp_agent_client/configs/$game/config.yaml" \
    env.input_modality="$input_modality" \
    agent.llm_name="$model" \
    agent.agent_type="$agent" \
    agent.prompt_path="mcp_agent_servers.$game.prompts.$input_modality.$agent"