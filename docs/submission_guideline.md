# Submission Guideline

If you want to submit your model and agent to the Orak [leaderboard](https://krafton-ai.github.io/orak-leaderboard/), please follow the below instructions.

## Model Submission 

1. Fork and clone the Orak repository (https://github.com/krafton-ai/Orak)
2. Make your local branch to edit 
```
git checkout -b submission/{yourmodel}-{username}
```
3. edit [llm.py](../src/mcp_agent_client/llms/llm.py), and if needed, make `{yourmodel}_utils.py` just like [openai_utils.py](../src/mcp_agent_client/llms/openai_utils.py)

- In `llm.py`, make sure to create `class YourModelBase()` following other `LLMBase()`.
- In `llm.py`, also make sure to edit `load_model()` to properly configure `{yourmodel}`.
- If your model is local/fine-tuned LLM served by huggingface, just share us the huggingface url by making `submission/{yourmodel}_README.md`.

4. Run your model, and share the log of your model with the default agent for each game

- Please use the `python` script like `bash scripts/leaderboard/python/{game}.sh`. It would be much easier to use to you than mcp.
- The log should be _automatically_ saved in `logs/{game_name}/{yourmodel}/{state_modality}/{default_agent}/{time}/`
- You should include the logs for all 12 games.
- You can only use `text` as the `{state_modality}`.

5. Write down anything you need to share at `submission/{yourmodel}_README.md`.

6. Commit your file and logs

```
git add src/mcp_agent_client/llm/llm.py
git add src/mcp_agent_client/llm/{yourmodel}_utils.py # if needed
git commit -m "new model submission"
git push origin submission/{yourmodel}-{username}
```

7. Create a pull request to the Orak repository with the new branch.


## Agentic Strategy Submission 


1. Fork and clone the Orak repository (https://github.com/krafton-ai/Orak)
2. Make your local branch to edit 
```
git checkout -b submission/{youragent}-{username}
```
3. edit [base_agent.py](../src/mcp_agent_client/base_agent.py), and add prompts in `src/mcp_agent_servers/{game_name}/{state_modality}/{youragent}/`

- Only modify `class BaselineAgent()`, and do not modify `class BaseAgent()`.
- In `class BaselineAgent()`, make your agentic module like `def your_agent(self, **kwargs)`.
- Add the corresponding prompts to activate your agent in `src/mcp_agent_servers/{game_name}/{state_modality}/{youragent}/` for all 12 games.
- Feel free to add/modify other files to support your agent, and describe details by making `submission/{youragent}_README.md`.
- Make sure your implementation do not hurt other agentic strategies (e.g., zeroshot, reflection, etc)


4. Run your agent, and share the log of your agent with at least one LLM for each game

- Please use the `python` script like `python scripts/play_game.py --config {config_path} agent.agent_type={youragent}`. It would be much easier to use to you than mcp.
- Verify the effectiveness of your agent with at least one LLM like `gpt-4o` and `llama-3.2-3B`.
- The log should be _automatically_ saved in `logs/{game_name}/gpt-4o/{state_modality}/{youragent}/{time}/`
- You should include the logs for all 12 games.
- You can only submit `text` as the `state_modality`.

5. Write down anything you need to share at `submission/{youragent}_README.md`.

6. Commit your file and logs

```
git add {all_your_modified_files}
git commit -m "new agent submission"
git push origin submission/{youragent}-{username}
```

7. Create a pull request to the Orak repository with the new branch.