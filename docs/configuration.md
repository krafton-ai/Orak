# ⚙️ Configuration Details

`./scripts/mcp_play_game.py` and `scripts/play_game.py` are configured using [OmegaConfig](https://github.com/omry/omegaconf). For each `{game}`, the evaluation is performed with the configs listed in `./src/mcp_agent_client/configs/{game}/config.yaml`. The configs are mainly categorized into `runner`, `env`, and `agent`, which we list some options below.

## Runner

| Parameter                 | Description                                                                                       | Default Value                             |
|---------------------------|---------------------------------------------------------------------------------------------------|-------------------------------------------|
| **runner.max_steps**            | Number of game steps used for evaluation              | `some int value`                                      |

## Env

| Parameter                 | Description                                                                                       | Default Value                             |
|---------------------------|---------------------------------------------------------------------------------------------------|-------------------------------------------|
| **env.task**            | Target task that should be completed by the LLM agent in each game              | `some string value`
| **env.input_modality**            | Modality of the game state passed to the LLM agent (`text`, `image`, `text_image`)          | `text`
| **env.custom_param**            | Any parameter needed to be used in each game          | `any value with any type`


## Agent

| Parameter                 | Description                                                                                       | Default Value                             |
|---------------------------|---------------------------------------------------------------------------------------------------|-------------------------------------------|
| **agent.llm_name**            | Name of the LLM used (`gpt-4o`, `gemini-2.5-pro`, `deepseek-r1`, `Qwen/Qwen2.5-7B-Instruct`, etc)              | `string value`
| **agent.api_key**            | API key needed to communicate your vllm sever        | `token-abc123`
| **agent.api_base_url**       | base URL needed to communicate your vllm sever       | `http://{your_vllm_url}:8001/v1`
| **agent.temperature**        | Temperature used for LLM inference             | `1.0`
| **agent.repetition_penalty** | Repetition penalty used for LLM inference      | `1.0`
| **agent.agent_type**         | agent type used in the game (`zeroshot_agent`, `reflection_agent`, etc)       | `default agent in each game`
| **agent.prompt_path**        | Path for prompt to play each game       | `mcp_agent_servers.{game}.prompts.{modality}.{agent}`
