# LLMs
# "gpt-4o-mini" "gpt-4o" "o3-mini" "claude-3-7-sonnet-20250219" "gemini-2.5-pro-preview-03-25" "deepseek-reasoner" 
# SLMs
# "meta-llama/Llama-3.2-1B-Instruct" "meta-llama/Llama-3.2-3B-Instruct" "Qwen/Qwen2.5-3B-Instruct" "Qwen/Qwen2.5-7B-Instruct" "nvidia/Nemotron-Mini-4B-Instruct" "nvidia/Mistral-NeMo-Minitron-8B-Instruct"

game="street_fighter"
input_modality="text" # (text, image, text_image) / currently supports only "text" modality

model1="gpt-4o-mini"
agent1="zeroshot_agent"

model2="gpt-4o"
agent2="zeroshot_agent"

# Define the absolute path to your gamingslm directory
# IMPORTANT: Replace this with the correct absolute path if it's different
GAMINGSLM_BASE_PATH="C:/Users/bjchoi92/refactor/gamingslm" # Using forward slashes for diambra
SF_ROMS_PATH="$GAMINGSLM_BASE_PATH/executables/streetfighter3/roms"

echo "Using ROM path: $SF_ROMS_PATH"
echo "Running with model: $model, agent: $agent, modality: $input_modality"

diambra run -r "$SF_ROMS_PATH" python scripts/play_game_multi.py \
    --config="./src/mcp_agent_client/configs/"$game"_multi/config.yaml" \
        env.input_modality="$input_modality" \
        agent1.llm_name="$model1" \
        agent1.agent_type="$agent1" \
        agent1.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent1" \
        agent2.llm_name="$model2" \
        agent2.agent_type="$agent2" \
        agent2.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent2"
