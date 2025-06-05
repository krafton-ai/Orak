# LLMs
# "gpt-4o-mini" "gpt-4o" "o3-mini" "claude-3-7-sonnet-20250219" "gemini-2.5-pro-preview-03-25" "deepseek-reasoner" 
# SLMs
# "meta-llama/Llama-3.2-1B-Instruct" "meta-llama/Llama-3.2-3B-Instruct" "Qwen/Qwen2.5-3B-Instruct" "Qwen/Qwen2.5-7B-Instruct" "nvidia/Nemotron-Mini-4B-Instruct" "nvidia/Mistral-NeMo-Minitron-8B-Instruct"

game="minecraft"
model="gpt-4o-mini"
agent="skill_management_agent"
input_modality="text" # (text, image, text_image)

# Note: you need to run each task below sequentially

# Task1 - crafting_table
uv run ./scripts/mcp_play_game.py \
    --config ./src/mcp_agent_client/configs/"$game"/config.yaml \
        env.task="craft 1 crafting table" \
        env.success_condition="crafting_table" \
        env.input_modality="$input_modality" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent"

'''
# Task2 - stone_pickaxe
uv run ./scripts/mcp_play_game.py \
    --config ./src/mcp_agent_client/configs/"$game"/config.yaml \
        env.task="craft 1 stone pickaxe" \
        env.success_condition="stone_pickaxe" \
        env.input_modality="$input_modality" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent"

# Task3 - furnace
uv run ./scripts/mcp_play_game.py \
    --config ./src/mcp_agent_client/configs/"$game"/config.yaml \
        env.task="craft 1 furnace" \
        env.success_condition="furnace" \
        env.input_modality="$input_modality" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent" 

# Task4 - bucket
uv run ./scripts/mcp_play_game.py \
    --config ./src/mcp_agent_client/configs/"$game"/config.yaml \
        env.task="craft 1 bucket" \
        env.success_condition="bucket" \
        env.input_modality="$input_modality" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent"
        
# Task5 - golden_sword
uv run ./scripts/mcp_play_game.py \
    --config ./src/mcp_agent_client/configs/"$game"/config.yaml \
        env.task="craft 1 golden sword" \
        env.success_condition="golden_sword" \
        env.input_modality="$input_modality" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent"

# Task6 - diamond_pickaxe
uv run ./scripts/mcp_play_game.py \
    --config ./src/mcp_agent_client/configs/"$game"/config.yaml \
        env.task="craft 1 diamond pickaxe" \
        env.success_condition="diamond_pickaxe" \
        env.input_modality="$input_modality" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent"
        
# Task7 - enchanting_table
uv run ./scripts/mcp_play_game.py \
    --config ./src/mcp_agent_client/configs/"$game"/config.yaml \
        env.task="craft 1 enchanting table" \
        env.success_condition="enchanting_table" \
        env.input_modality="$input_modality" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent"
        
# Task8 - nether_portal
uv run ./scripts/mcp_play_game.py \
    --config ./src/mcp_agent_client/configs/"$game"/config.yaml \
        env.task="craft 1 nether portal" \
        env.success_condition="nether_portal" \
        env.input_modality="$input_modality" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=mcp_agent_servers."$game".prompts."$input_modality"."$agent"
