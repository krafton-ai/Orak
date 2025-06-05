import collections
import collections.abc
import time
from pathlib import Path

for type_name in collections.abc.__all__:
    setattr(collections, type_name, getattr(collections.abc, type_name))

import os
import logging

from anthropic import Anthropic
from anthropic.types import Message as AnthropicMessage
from openai.types.chat.chat_completion import (
    ChatCompletion as OpenAIChatCompletion,
)
from openai.types.chat.chat_completion import (
    ChatCompletionMessage as OpenAIChatCompletionMessage,
)
from openai.types.chat.chat_completion import Choice as OpenAIChoice
from openai.types.chat.chat_completion import (
    CompletionUsage as OpenAICompletionUsage,
)
from tenacity import retry, stop_after_attempt, wait_random_exponential

logger = logging.getLogger(__name__)

# Message(id='msg_01VjSSR3zifDHfwgfFUmk7oa',
#   content=[ContentBlock(text="It's nice to meet you! I'm Claude, an AI assistant. How are you doing today?",
#   type='text')], model='claude-3-opus-20240229',
#   role='assistant', stop_reason='end_turn',
#   stop_sequence=None, type='message',
#   usage=Usage(input_tokens=12, output_tokens=24))

STOP_REASON_MAPPING = {
    "end_turn": "stop",
    "max_tokens": "length",
    "stop_sequence": "content_filter",
    "tool_use": "tool_calls",
}


def setup_anthropic(key_path: str | Path = "src/mcp_agent_servers/keys/anthropic-key/key.env") -> str:
    with open(key_path, "r") as f:
        api_key = f.read().strip()
    os.environ["ANTHROPIC_API_KEY"] = api_key
    return api_key

try:
    client = Anthropic(api_key=setup_anthropic())
except Exception as e:
    print(f"Exception occurred while setting up Anthropic client: {e}")
    client = None


def port_to_openai(response: AnthropicMessage) -> OpenAIChatCompletion:
    openai_choices = []
    for i, choice in enumerate(response.content):
        openai_message = OpenAIChatCompletionMessage(
            content=choice.text,
            role=response.role,
            function_call=None,
            tool_calls=None,
        )
        openai_choice = OpenAIChoice(
            finish_reason=STOP_REASON_MAPPING[response.stop_reason],
            index=i,
            logprobs=None,
            message=openai_message,
        )
        openai_choices.append(openai_choice)

    openai_response = OpenAIChatCompletion(
        id=response.id,
        choices=openai_choices,
        created=int(time.time()),
        model=response.model,
        object="chat.completion",
        usage=OpenAICompletionUsage(
            completion_tokens=response.usage.input_tokens,
            prompt_tokens=response.usage.output_tokens,
            total_tokens=(
                response.usage.input_tokens + response.usage.output_tokens
            ),
        ),
    )
    return openai_response


@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(5))
def chat_completion_request(
    messages, model: str = "gpt-3.5-turbo-0613", **kwargs
) -> OpenAIChatCompletion | None:
    json_data = {"model": model, "messages": messages}
    # recap message for anthropic
    claude_messages = []
    for msg in messages:
        if msg["role"] == "system":
            json_data.update({"system": msg["content"]})
        else:
            if isinstance(msg["content"], str):
                new_packet = {"role": msg["role"], "content": msg["content"]}
                claude_messages.append(new_packet)
            elif isinstance(msg["content"], list):
                new_content = []
                for content in msg["content"]:
                    if content["type"] == "text":
                        new_content.append(content)
                    elif content["type"] == "image_url":
                        new_content.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": content["image_url"]["url"][len("data:image/png;base64,"):]
                                }
                            }
                        )
                new_packet = {
                    "role": msg["role"],
                    "content": new_content,
                }
                claude_messages.append(new_packet)
            else:
                raise ValueError(
                    f"Unsupported message content type: {type(msg['content'])}"
                )

    json_data["messages"] = claude_messages

    if "stop" in kwargs.keys() and kwargs["stop"] is not None:
        json_data.update({"stop": kwargs["stop"]})
    if "temperature" in kwargs.keys() and kwargs["temperature"] is not None:
        json_data.update({"temperature": kwargs["temperature"]})
    if "max_tokens" in kwargs.keys():
        if kwargs["max_tokens"] is not None:
            json_data.update({"max_tokens": kwargs["max_tokens"]})
        else:
            json_data.update({"max_tokens": 4096})
    if "stream" in kwargs.keys():
        if kwargs["max_tokens"] is not None:
            json_data.update({"max_tokens": kwargs["max_tokens"]})
        else:
            json_data.update({"stream": True})

    try:
        response = client.messages.create(**json_data)
        return port_to_openai(response)
    except Exception as e:
        logger.info("Unable to generate ChatCompletion response")
        logger.info(f"Exception: {e}")
        raise e


if __name__ == "__main__":
    # api test
    messages = [
        {"role": "system", "content": "Say hi."},
        {"role": "user", "content": "Hello."},
    ]
    message = chat_completion_request(
        messages,
        model="claude-3-opus-20240229",
        max_tokens=100,
        temperature=0.5,
    )
    print(message)
