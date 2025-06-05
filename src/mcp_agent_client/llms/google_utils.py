from typing import List, Dict, Union
import os
import logging
import base64

from google.oauth2 import service_account
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def setup_gemini(
    service_account_path: str = "src/mcp_agent_servers/keys/google-key/gemini_gcp.json",
    project_id: str = "gamebench-456108",
    # project_id: str = "gamingslm",
    location: str = "us-central1",
) -> genai.Client:
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials = service_account.Credentials.from_service_account_file(
        service_account_path, scopes=scopes
    )
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=location,
        credentials=credentials,
    )
    return client

try:
    client = setup_gemini()
except Exception as e:
    print(f"Exception occurred while setting up Gemini client: {e}")
    client = None


class Message:
    def __init__(self, role: str, content: str):
        self.role = role 
        self.content = content

class Choice:
    def __init__(self, message: Message):
        self.message = message

class GeminiChatCompletionResponse:
    def __init__(self, text: str, role: str):
        self.choices = [Choice(Message(role=role, content=text))] 
        self.usage = None  # unavailable in gemini


# def chat_completion_request(
#     model: str,
#     messages: List[Dict[str, str]],
#     temperature: float = 0.2,
#     top_p: float = 0.8,
#     max_tokens: int = 1024,
#     stream: bool = False,
# ) -> GeminiChatCompletionResponse:

#     system_prompt = None
#     contents = []

#     for m in messages:
#         if m["role"] == "system" and system_prompt is None:
#             system_prompt = m["content"]
#         else:
#             if isinstance(m["content"], str):
#                 contents.append(
#                     types.Content(
#                         role=m["role"],
#                         parts=[types.Part.from_text(text=m["content"])]
#                     )
#                 )
#             elif isinstance(m["content"], list):
#                 for part in m["content"]:
#                     if part["type"] == "text":
#                         contents.append(
#                             types.Content(
#                                 role=m["role"],
#                                 parts=[types.Part.from_text(text=part["text"])]
#                             )
#                         )
#                     elif part["type"] == "image_url":
#                         base64_image = part["image_url"]["url"][len("data:image/png;base64,"):]
#                         image_bytes = base64.b64decode(base64_image)
#                         contents.append(
#                             types.Content(
#                                 role=m["role"],
#                                 parts=[types.Part.from_bytes(data=image_bytes, mime_type="image/png")]
#                             )
#                         )
#                     else:
#                         raise ValueError("Content must be a string or list of strings.")

#     if system_prompt is None:
#         system_prompt = ""

#     generate_content_config = types.GenerateContentConfig(
#         temperature=temperature,
#         top_p=top_p,
#         max_output_tokens=max_tokens,
#         response_modalities=["TEXT"],
#         safety_settings=[],
#         system_instruction=[types.Part(text=system_prompt)],
#     )

#     full_text = ""
#     response_role = ""  # default role

#     if stream:
#         for chunk in client.models.generate_content_stream(
#             model=model,
#             contents=contents,
#             config=generate_content_config,
#         ):
#             if hasattr(chunk, "text") and chunk.text:
#                 full_text += chunk.text
#                 response_role = "assistant" 
#     else:
#         max_retries = 100
#         for attempt in range(max_retries):
#             full_text = ""
#             response_role = ""
#             response = client.models.generate_content(
#                 model=model,
#                 contents=contents,
#                 config=generate_content_config,
#             )
#             if hasattr(response, "candidates") and response.candidates:
#                 for candidate in response.candidates:
#                     if candidate.content.parts:
#                         for part in candidate.content.parts:
#                             if hasattr(part, "text") and part.text:
#                                 full_text += part.text
#                                 response_role = "assistant"

#             if full_text and response_role:
#                 break
#             logger.info(f"[Retry {attempt+1}] Empty response. Retrying...")

#     return GeminiChatCompletionResponse(text=full_text, role=response_role)

def chat_completion_request(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    top_p: float = 0.8,
    max_tokens: int = 1024,
    stream: bool = False,
) -> GeminiChatCompletionResponse:

    system_prompt = None
    contents = []

    for m in messages:
        if m["role"] == "system" and system_prompt is None:
            system_prompt = m["content"]
        else:
            if isinstance(m["content"], str):
                contents.append(
                    types.Content(
                        role=m["role"],
                        parts=[types.Part.from_text(text=m["content"])]
                    )
                )
            elif isinstance(m["content"], list):
                for part in m["content"]:
                    if part["type"] == "text":
                        contents.append(
                            types.Content(
                                role=m["role"],
                                parts=[types.Part.from_text(text=part["text"])]
                            )
                        )
                    elif part["type"] == "image_url":
                        base64_image = part["image_url"]["url"][len("data:image/png;base64,"):]
                        image_bytes = base64.b64decode(base64_image)
                        contents.append(
                            types.Content(
                                role=m["role"],
                                parts=[types.Part.from_bytes(data=image_bytes, mime_type="image/png")]
                            )
                        )
                    else:
                        raise ValueError("Content must be a string or list of strings.")

    if system_prompt is None:
        system_prompt = ""

    generate_content_config = types.GenerateContentConfig(
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_tokens,
        response_modalities=["TEXT"],
        safety_settings=[],
        system_instruction=[types.Part(text=system_prompt)],
    )

    full_text = ""
    response_role = ""  # default role

    if stream:
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if hasattr(chunk, "text") and chunk.text:
                full_text += chunk.text
                response_role = "assistant"
    else:
        max_retries = 10
        for attempt in range(max_retries):
            try:
                full_text = ""
                response_role = ""
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                )
                if hasattr(response, "candidates") and response.candidates:
                    for candidate in response.candidates:
                        if candidate.content.parts:
                            for part in candidate.content.parts:
                                if hasattr(part, "text") and part.text:
                                    full_text += part.text
                                    response_role = "assistant"

                if full_text and response_role:
                    break
                print(f"[Retry {attempt+1}] Empty response. Retrying...")
            except Exception as e:
                import time
                print(f"[Retry {attempt + 1}] Unexpected error: {e}. Retrying...")
                time.sleep(2 ** attempt)

    return GeminiChatCompletionResponse(text=full_text, role=response_role)