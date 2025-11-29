Markdown

# Mario Maker (Super Mario Agent)

## Model Information
- **Model Name:** mario-maker
- **Base Model:** Meta-Llama-3-8B-Instruct
- **Method:** Fine-tuned using Axolotl on `super-mario-bros-levels-discrete` dataset.
- **Format:** GGUF (Quantized)

## 1. Installation & Environment
This agent requires specific library versions (especially `numpy<2.0`) to avoid compatibility issues with `nes-py`.

```bash
# Install dependencies (This installs numpy==1.26.4 automatically)
pip install -r requirements.txt
2. Model Setup (Ollama)
Since this is a custom GGUF model, you need to create it manually in Ollama.

Step 1: Download Model
Download the mario.gguf file from the link below and place it in the project root.

Download Link: https://huggingface.co/kaknafkanka/mario-maker-gguf/tree/main

Step 2: Create Modelfile
Create a file named Modelfile in the root directory with the following content:

Dockerfile

FROM ./mario.gguf

TEMPLATE """<|start_header_id|>system<|end_header_id|>

{{ .System }}<|eot_id|><|start_header_id|>user<|end_header_id|>

{{ .Prompt }}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{{ .Response }}<|eot_id|>"""

SYSTEM """You are a level designer for Super Mario Bros.
When the user provides a description, output the level data as a specific array format like [[0,0,...]].
Do not add unnecessary explanations."""
Step 3: Register Model & Create Alias
Run the following commands to register the model and create the alias required by the script.

Bash

# Create the base model
ollama create mario-maker -f Modelfile

# Create an alias to enable API mode (Important!)
ollama cp mario-maker me/mario-maker
3. How to Run
Run the agent using the following command:

Bash

python scripts/play_game.py ^
    --config src/mcp_agent_client/configs/super_mario/config.yaml ^
    env.input_modality=text ^
    agent.llm_name=me/mario-maker ^
    agent.agent_type=zeroshot_agent ^
    agent.prompt_path=mcp_agent_servers.super_mario.prompts.text.zeroshot_agent