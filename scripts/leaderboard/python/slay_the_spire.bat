@echo off
REM ========================================
REM IMPORTANT:
REM Do not run this script directly.
REM This script is executed directly by the game launcher.
REM For more details, see docs/slay_the_spire_setup.md.
REM ========================================

REM LLMs
REM "gpt-4o-mini" "gpt-4o" "o3-mini" "claude-3-7-sonnet-20250219" "gemini-2.5-pro-preview-03-25" "deepseek-reasoner"
REM SLMs
REM "meta-llama/Llama-3.2-1B-Instruct" "meta-llama/Llama-3.2-3B-Instruct" "Qwen/Qwen2.5-3B-Instruct" "Qwen/Qwen2.5-7B-Instruct" "nvidia/Nemotron-Mini-4B-Instruct" "nvidia/Mistral-NeMo-Minitron-8B-Instruct"

SET game=slay_the_spire
SET model=gpt-4o-mini
SET agent=reflection_planning_agent
SET input_modality=text

CALL conda activate gaming_slm
cd \path\to\gamingslm

python scripts\play_game.py ^
    --config="./src/mcp_agent_client/configs/%game%/config.yaml" ^
    env.input_modality="%input_modality%" ^
    agent.llm_name="%model%" ^
    agent.agent_type="%agent%" ^
    agent.prompt_path="mcp_agent_servers.%game%.prompts.%input_modality%.%agent%"