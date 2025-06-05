import os
import logging
from typing import Any, Dict, Iterable, List, Union

import numpy as np
import tiktoken
from anthropic.types import MessageParam
from openai import OpenAI, Stream
from openai.types import Completion as OpenAICompletion
from openai.types.chat.chat_completion import (
    ChatCompletion as OpenAIChatCompletion,
)
from openai.types.chat.chat_completion import (
    ChatCompletionMessage as OpenAIChatCompletionMessage,
)
from openai.types.chat.chat_completion import Choice as OpenAIChoice
from transformers import AutoTokenizer

from .openai_utils import (
    MoneyManager, 
    chat_completion_request, 
    completion_request,
)
from .anthropic_utils import (
    chat_completion_request as anthropic_chat_completion_request,
)
from .deepseek_utils import (
    chat_completion_request as deepseek_chat_completion_request,
)
from .google_utils import (
    chat_completion_request as google_chat_completion_request,
)

from .utils import CompletionFunc, Message, chat_messages_to_prompt
from .constants import llama_chat_template

#os.environ["TRANSFORMERS_CACHE"] = "./loaded_model_info"

logger = logging.getLogger(__name__)

def load_model(
    model: str,
    temperature: float = 1.0,
    repetition_penalty: float = 0,
    api_key: str = None,
    api_base_url: str = None,
) -> Dict[str, Any]:
    if "gpt-3.5" in model:
        default_model = model
        if "16k" in model:
            output_budget = 4096
        else:
            output_budget = 1024
        model_type = "chatgpt"
    elif "gpt-4" in model or "o1" in model or "o3" in model:
        default_model = model
        output_budget = 64000
        model_type = "chatgpt"
    elif "claude" in model:
        default_model = model
        output_budget = 64000
        model_type = "claude"
    elif "deepseek" in model:
        default_model = model
        output_budget = 1024
        model_type = "deepseek"
    elif "gemini" in model:
        default_model = model
        output_budget = 64000
        model_type = "gemini"
    else:
        default_model = model
        model_type = "local"
        output_budget = 1024

    model = default_model

    logger.info(f"model: {model}")
    logger.info(f"model_type: {model_type}")

    # Main model
    ctx_manager = MoneyManager(model=model)

    if model_type == "chatgpt":
        llm = ChatGPTBase(
            model=model,
            ctx_manager=ctx_manager,
            desired_output_length=output_budget,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
        )
        enc = tiktoken.get_encoding("cl100k_base")
    elif model_type == "claude":
        llm = ClaudeBase(
            model=model,
            ctx_manager=ctx_manager,
            desired_output_length=output_budget,
            temperature=temperature,
        )
        # DISCLAIMER: This is not compatible with claude, but only used to count the number of tokens
        # As claude-3 can get 1,000,000 tokens as inputs, we do not need to prune the input tokens now.
        # Furthermore, there is no simple useful package for claude now.
        # Therefore, we just use openai tokenizer for a while.
        enc = tiktoken.get_encoding("cl100k_base")
    elif model_type == "deepseek":
        llm = DeepseekBase(
            model=model,
            ctx_manager=ctx_manager,
            desired_output_length=output_budget,
            temperature=temperature,
        )
        enc = tiktoken.get_encoding("cl100k_base")
    elif model_type == "gemini":
        llm = GeminiBase(
            model=model,
            ctx_manager=ctx_manager,
            desired_output_length=output_budget,
            temperature=temperature,
        )
        enc = tiktoken.get_encoding("cl100k_base")
    elif model_type == "local":
        assert (api_key is not None) and (api_base_url is not None), "API key and base URL must be provided for local models."
        llm = LocalBase(
            model=model,
            ctx_manager=ctx_manager,
            desired_output_length=output_budget,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            api_key=api_key,
            api_base_url=api_base_url,
        )
        enc = tiktoken.get_encoding("cl100k_base")  # llm.engine.get_tokenizer()
    else:
        raise NotImplementedError

    return {
        "model_name": model,
        "llm": llm,
        "tokenizer": enc,
        "ctx_manager": ctx_manager,
    }

# ChatGPT having tools
class ChatGPTBase:
    def __init__(
        self,
        model: str,
        tool: Iterable[CompletionFunc] | None = None,
        ctx_manager: MoneyManager | None = None,
        desired_output_length: int = 512,
        temperature: float = 1.0,
        repetition_penalty: float = 1.0,
    ):
        self.model = model
        self.tool = tool
        assert ctx_manager is not None
        self.ctx_manager = ctx_manager
        self.enc = tiktoken.get_encoding("cl100k_base")
        if "gpt-3.5" in self.model:
            if "16k" in self.model or "1106" in self.model:
                self.max_budget = 16384
            else:
                self.max_budget = 4096
        elif "gpt-4-1106-preview" in self.model:
            self.max_budget = 128000
        elif "gpt-4" in self.model:
            self.max_budget = 128000
        elif "o1" in self.model:
            self.max_budget = 128000
        elif "o3" in self.model:
            self.max_budget = 128000
        else:
            raise NotImplementedError()
        self.desired_output_length = desired_output_length
        self.temperature = temperature
        self.repetition_penalty = (repetition_penalty - 1.0,)

        if "o1" in self.model or "o3" in self.model:
            self.temperature = None
            logger.info(f"Temperature is not supported and set to None for reasoning models (model name: {self.model}).")

    def cutoff(self, message: Union[str, dict], budget: int) -> str:
        if isinstance(message, dict):
            # contain visual input
            # TODO: implement this
            return message

        tokens = self.enc.encode(message)
        if len(tokens) > budget:
            message = self.enc.decode(tokens[:budget])
        return message

    def manage_length(self, messages: List[Message]) -> None:
        # TODO: implement this 
        # last_message = messages[-1]["content"]
        # if len(messages) > 1:
        #     previous_tokens_length = 0
        #     for msg in messages[:-1]:
        #         if "content" in msg.keys() and msg["content"] is not None:
        #             previous_tokens_length += len(
        #                 self.enc.encode(msg["content"])
        #             )
        #         elif (
        #             "function_call" in msg.keys()
        #             and msg["function_call"] is not None
        #         ):
        #             previous_tokens_length += (
        #                 len(self.enc.encode(msg["function_call"]["arguments"]))
        #                 + 30
        #             )
        # else:
        #     previous_tokens_length = 0
        # budget = (
        #     self.max_budget
        #     - self.desired_output_length
        #     - previous_tokens_length
        # )
        # messages[-1]["content"] = self.cutoff(last_message, budget)
        pass

    def chat(
        self,
        messages: List[Message],
        function: List[CompletionFunc | None] = [None],
        disable_function: bool = False,
        **kwargs,
    ):
        self.manage_length(messages)
        if self.tool is not None and not disable_function:
            response = chat_completion_request(
                messages,
                self.tool.functions,
                model=self.model,
                temperature=self.temperature,
                frequency_penalty=self.repetition_penalty,
                **kwargs,
            )
        else:
            response = chat_completion_request(
                messages,
                model=self.model,
                temperature=self.temperature,
                **kwargs,
            )
        self.ctx_manager(response)
        return response

    def __call__(
        self,
        messages: List[Message],
        disable_function: bool = False,
        stop: List[str] | str | None = None,
        n: int = 1,
        max_tokens: int | None = None,
        **kwargs,
    ):
        response = self.chat(
            messages,
            disable_function=disable_function,
            stop=stop,
            n=n,
            max_tokens=max_tokens,
            **kwargs,
        )

        full_message = response.choices[0]
        if full_message.finish_reason == "function_call":
            messages.append(full_message["message"])
            func_results = self.tool.call_function(messages, full_message)

            try:
                response = self.chat(messages, disable_function=True)
                return {
                    "response": response,
                    "function_results": func_results,
                }
            except Exception as e:
                print(type(e))
                raise Exception("Function chat request failed")
        else:
            return {
                "response": response,
                "function_results": None,
            }


# Claude Models
class ClaudeBase:
    def __init__(
        self,
        model: str,
        ctx_manager: MoneyManager = None,
        desired_output_length: int = 512,
        temperature: float = 1.0,
    ):
        self.model = model
        assert ctx_manager is not None
        self.ctx_manager = ctx_manager
        self.enc = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 8192
        self.desired_output_length = desired_output_length
        self.temperature = temperature

    def chat(self, messages: List[MessageParam], *args, **kwargs):
        response = anthropic_chat_completion_request(
            messages, model=self.model, temperature=self.temperature, **kwargs
        )
        self.ctx_manager(response)
        return response

    def __call__(
        self,
        messages: List[MessageParam],
        disable_function: bool = False,
        stop: List[str] | str | None = None,
    ):
        response = self.chat(
            messages,
            disable_function=disable_function,
            stop=stop,
            max_tokens=self.max_tokens,
        )
        return {
            "response": response,
            "function_results": None,
        }


# Deepseek
class DeepseekBase:
    def __init__(
        self,
        model: str,
        ctx_manager=None,
        desired_output_length: int = 512,
        temperature: float = 1.0,
    ):
        self.model = model
        assert ctx_manager is not None
        self.ctx_manager = ctx_manager
        self.max_tokens = desired_output_length
        self.temperature = temperature
        self.stream = False

    def chat(self, messages: List[dict], *args, **kwargs):
        response = deepseek_chat_completion_request(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=self.stream,
            **kwargs,
        )
        self.ctx_manager(response)
        return response

    def __call__(
        self,
        messages: List[dict],
        disable_function: bool = False,
        stop: Union[List[str], str, None] = None,
    ):
        response = self.chat(
            messages,
            stop=stop,
        )
        return {
            "response": response,
            "function_results": None,
        }
    
# Gemini
class GeminiBase:
    def __init__(
        self,
        model: str,
        ctx_manager=None,
        desired_output_length: int = 512,
        temperature: float = 1.0,
    ):
        self.model = model
        assert ctx_manager is not None
        self.ctx_manager = ctx_manager
        self.max_tokens = 8192
        self.desired_output_length = desired_output_length
        self.temperature = temperature

    def chat(self, messages: List[dict], *args, **kwargs):
        response = google_chat_completion_request(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs,
        )
        #self.ctx_manager(response) # No response.usage in gemini
        return response

    def __call__(
        self,
        messages: List[dict],
        disable_function: bool = False,
    ):
        response = self.chat(
            messages,
        )
        return {
            "response": response,
            "function_results": None,
        }

# Llama2 Model Base
class LocalBase:
    def __init__(
        self,
        model,
        api_key,
        api_base_url,
        tool=None,
        ctx_manager: MoneyManager | None = None,
        desired_output_length: int = 1024,
        temperature: float = 1.0,
        repetition_penalty: float = 1.0,
    ):
        self.model = model
        self.tool = tool
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base_url,
        )
        assert ctx_manager is not None
        self.ctx_manager = ctx_manager
        self.enc = tiktoken.get_encoding("cl100k_base")
        self.max_budget = 8192
        self.output_budget = 1024
        self.desired_output_length = desired_output_length
        self.temperature = temperature
        self.repetition_penalty = repetition_penalty
        
        finetune_base_model = [
            "meta-llama/Llama-3.2-1B-Instruct",
            "meta-llama/Llama-3.2-3B-Instruct",
        ]
        is_finetune = False
        for base_model in finetune_base_model:
            if self.model.startswith(base_model):
                is_finetune = True
                self.tok = AutoTokenizer.from_pretrained(base_model)
                break
        if not is_finetune:
            self.tok = AutoTokenizer.from_pretrained(self.model)

        if self.model.startswith("meta-llama/Llama-3.2"):
            self.tok.chat_template = llama_chat_template

    def cutoff(self, message: str, budget: int) -> str:
        tokens = self.enc.encode(message)
        if len(tokens) > budget:
            message = self.enc.decode(tokens[:budget])
        return message

    def manage_length(self, messages: List[Message]) -> None:
        last_message = messages[-1]["content"]
        if len(messages) > 1:
            previous_tokens_length = 0
            for msg in messages[:-1]:
                if "content" in msg.keys() and msg["content"] is not None:
                    previous_tokens_length += len(
                        self.enc.encode(msg["content"])
                    )
        else:
            previous_tokens_length = 0
        budget = (
            self.max_budget
            - self.desired_output_length
            - previous_tokens_length
        )
        messages[-1]["content"] = self.cutoff(last_message, budget)

    def chat(
        self, messages: List[Message], lora=None, **kwargs
    ) -> Stream[OpenAICompletion] | None:
        self.manage_length(messages)

        # turn messages to prompt
        prompt = chat_messages_to_prompt(
            self.tok,
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        response = completion_request(
            prompt,
            model=self.model if lora is None else lora,
            temperature=self.temperature,
            client=self.client,
            **kwargs,
        )
        self.ctx_manager(response)
        return response

    def __call__(
        self,
        messages: List[Message],
        disable_function: bool = False,
        stop: List[str] = [
            "### USER",
            "### ASSISTANT",
            "### SYSTEM",
            "<extra_id_1>",
            #"###",
            #"#",
        ],
        n: int = 1,
        max_tokens: int | None = None,
        **kwargs,
    ) -> Dict[str, Any]:
        if "gemma" in self.model:  # Gemma model do not have the system prompt!
            if messages[0]["role"] == "system":
                system_message = messages[0]
                messages = messages[1:]
            for message in messages:
                if message["role"] == "user":
                    message[
                        "content"
                    ] = f'{system_message["content"]}\n{message["content"]}'

        if "SmolLM" in self.model:
            new_messages = []
            if messages[0]["role"] == "system":
                new_user_message = (
                    "\n\n".join(
                        [message["content"] for message in messages[1:-2]]
                    )
                    if messages[-1]["role"] == "assistant"
                    else "\n\n".join(
                        [message["content"] for message in messages[1:-1]]
                    )
                )
                new_messages.append(messages[0])
            else:
                new_user_message = (
                    "\n\n".join(
                        [message["content"] for message in messages[:-2]]
                    )
                    if messages[-1]["role"] == "assistant"
                    else "\n\n".join(
                        [message["content"] for message in messages[:-1]]
                    )
                )
            if messages[-1]["role"] == "assistant":
                new_messages.append(
                    {
                        "role": "user",
                        "content": f"{new_user_message}\n\n{messages[-2]['content']}",
                    }
                )
                new_messages.append(messages[-1])
            else:
                new_messages.append(
                    {
                        "role": "user",
                        "content": f"{new_user_message}\n\n{messages[-1]['content']}",
                    }
                )
            messages = new_messages

        # turn messages to prompt
        prompt = chat_messages_to_prompt(
            self.tok,
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        desired_output_length = min(
            self.desired_output_length,
            self.max_budget - len(self.enc.encode(prompt)),
        )  #  - 516
        # print(desired_output_length, self.max_budget - len(self.enc.encode(prompt))) # if max_tokens is None else max_tokens
        response = self.chat(
            messages,
            disable_function=disable_function,
            stop=stop,
            n=n,
            max_tokens=desired_output_length,
            repetition_penalty=self.repetition_penalty,
            **kwargs,
        )
        choices = []
        for choice in response.choices:
            choices.append(
                OpenAIChoice(
                    message=OpenAIChatCompletionMessage(
                        content=choice.text,
                        role="assistant",
                    ),
                    finish_reason=choice.finish_reason,
                    index=choice.index,
                    logprobs=choice.logprobs,
                    stop_reason=choice.stop_reason,
                )
            )
        return_response = OpenAIChatCompletion(
            id=response.id,
            choices=choices,
            created=response.created,
            model=response.model,
            object="chat.completion",
        )
        return {
            "response": return_response,
            "function_results": None,
        }
