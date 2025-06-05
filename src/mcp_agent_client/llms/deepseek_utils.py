import os
from openai import OpenAI
from openai.types.chat import ChatCompletion
import time

def setup_deepseek(key_path: str = "src/mcp_agent_servers/keys/deepseek-key/key.env") -> str:
    with open(key_path, "r") as f:
        api_key = f.read().strip()
    os.environ["DEEPSEEK_API_KEY"] = api_key
    return api_key

try:
    client = OpenAI(
            api_key=setup_deepseek(),
            base_url="https://api.deepseek.com"
        )
except Exception as e:
    print(f"Exception occurred while setting up DeepSeek client: {e}")
    client = None

def chat_completion_request(
    messages,
    model: str = "deepseek-reasoner",
    temperature: float = 1.0,
    max_tokens: int = 8192,
    stop=None,
    stream: bool = False,
    **kwargs
) -> ChatCompletion:
    
    max_retries = 10
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                stop=stop,
                **kwargs
            )
            return response
        except Exception as e:
            if attempt < max_retries-1:
                print(f"[Warning] chat_completion_request failed (attempt {attempt+1}), retrying...")
                time.sleep(0.5)
                continue
            else:
                print(f"[Error] chat_completion_request failed after {max_retries} attempts.")
                raise e
