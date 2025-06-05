from typing import Any, Dict, TypeAlias
from openai.types.chat import completion_create_params

CompletionFunc: TypeAlias = completion_create_params.Function
CompletionFuncCall: TypeAlias = completion_create_params.FunctionCall
Message: TypeAlias = Dict[str, Any]

def chat_messages_to_prompt(
    tokenizer,
    chat_messages,
    tokenize=False,
    return_dict=False,
    add_generation_prompt=True,
    max_length=None,
):
    for message in chat_messages:
        if message["role"] == "user" and isinstance(message["content"], list):
            assert all(c["type"] == "text" for c in message["content"]), (
                "Only text type is supported in the user message. "
                f"Got {message['content']} instead."
            )

            message["content"] = "".join(
                [c["text"] for c in message["content"]]
            )

    if tokenizer.chat_template is not None:
        continue_final_message = False
        if chat_messages and chat_messages[-1]["role"] == "assistant":
            if add_generation_prompt:
                continue_final_message = True
                add_generation_prompt = False

        return tokenizer.apply_chat_template(
            chat_messages,
            tokenize=tokenize,
            return_dict=return_dict,
            max_length=max_length,
            add_generation_prompt=add_generation_prompt,
            continue_final_message=continue_final_message,
        )
    else:
        text_prompt = ""
        for message in chat_messages:
            if message["role"] == "system":
                _prompt = f'### SYSTEM\n{message["content"]}\n'
            elif message["role"] == "user":
                _prompt = f'### USER\n{message["content"]}\n'
            else:
                _prompt = f'### ASSISTANT\n{message["content"]}\n'
            text_prompt += _prompt

        if add_generation_prompt:
            text_prompt += f"### ASSISTANT\n"

        if not tokenize:
            return text_prompt

        return tokenizer(
            text_prompt,
            return_dict=return_dict,
            max_length=max_length,
        )