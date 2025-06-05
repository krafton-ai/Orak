import importlib
import sys
import os
import json
from datetime import datetime
import omegaconf
import logging
import base64
from PIL import Image
from io import BytesIO
from typing import Dict, Optional
from dataclasses import field

from mcp.server.fastmcp import FastMCP
from mcp_agent_servers.agent_types import AGENT_MODULES

from mcp_agent_servers.memory import GenericMemory
from mcp_agent_servers.skill_manager import SkillManager

logger = logging.getLogger(__name__)

PREFIXS = {
    "self_reflection": {
        "self_reflection": "### Self_reflection", # Stardew Valley
        "self_reflection_summary": "### Self_reflection_summary", # Stardew Valley
        "critique": "### Critique", # Minecraft
        "success": "### Success", # Minecraft
        "analysis": "### Analysis", # Pwaat
    },
    "knowledge_retrieval": {
        "knowledge": "### Knowledge" # Minecraft
    },
    "subtask_planning": {
        "history_summary": "### History_summary", # Stardew Valley
        "subtask_reasoning": "### Subtask_reasoning", # Stardew Valley
        "subtask_description": "### Subtask", # Stardew Valley, Pwaat
        "subtask": "### Next_subtask", # Minecraft
    },
    "skill_management": {
        "skill_description": "### Skill_description", # Minecraft
        "retrieved_skills": "### Skill_retrieval" # Minecraft - Not_in_use; placeholder for local_memory update
    },
    "long_term_management": {
        "clue_extraction": "### Clue_Extraction", # Pwaat
        "saving": "### Saving" # Pwaat
    },
    "history_summarization":{
        "short_term_summary": "### Short_term_summary", # Pokemon
    },
    "memory_management":{
        "relevant_memory": "", # Pokemon
    },
    "action_execution":{
        "short_term_history": "" # Pokemon
    },
    "action_inference": {
        "action": "### Actions", # All Games
        "reasoning": "### Reasoning", # Pwaat
        "action_reasoning": "### Action_reasoning", # Pokemon
        "lessons_learned": "### Lessons_learned", # Pokemon
        "state_summary": "### State_summary", # Pokemon
    }
}

def load_prompt(prompt_path, module):
    module_name = f"{prompt_path}.{module}"
    _module = importlib.import_module(module_name)
    prompt = getattr(_module, "PROMPT")
    return prompt

def _is_line_key_candidate(line, prefixs):
    # Sort the prefixes by length to prevent long prefixes from matching shorter ones
    sorted_prefixes = sorted(prefixs.items(), key=lambda x: -len(x[1]))

    line = line.strip()
    for key, prefix in sorted_prefixes:
        if line.startswith(prefix):
            return True, key
    return False, None

# Parses the semi-formatted text from model response
def parse_semi_formatted_text(text, prefixs):
    lines = text.split("\n")

    lines = [line.rstrip() for line in lines if line.rstrip()]
    result_dict = {}
    current_key = None
    current_value = []

    for line in lines:
        is_key, key_candidate = _is_line_key_candidate(line, prefixs)

        if is_key:
            if current_key:
                result_dict[current_key] = "\n".join(current_value).strip()

            current_key = key_candidate.replace(" ", "_").lower()
            current_value = []
        else:
            line = line.strip()
            current_value.append(line)

    # Process the last key
    result_dict[current_key] = "\n".join(current_value).strip()

    return result_dict

def agent_get_local_memory(agent, game_info: Optional[list] = None) -> dict:
    local_memory = {}
    local_memory.update(game_info)

    local_memory["cur_state_str"] = agent.memory.get_last("observation")
    # update every prefix to local_memory
    for _, dict in PREFIXS.items():
        for key in dict:
            if key in local_memory and agent.memory.get_last(key) is None: # To not update "subtask" to None in zeroshot_agent
                continue
            else:
                local_memory[key] = agent.memory.get_last(key)

    if len(agent.memory.get_all("observation")) > 1:
        local_memory["prev_state_str"] = agent.memory.get_all("observation")[-2]
    if len(agent.memory.get_all("image")) > 0:
        local_memory["cur_image"] = agent.memory.get_last("image")
    if len(agent.memory.get_all("image")) > 1:
        local_memory["prev_image"] = agent.memory.get_all("image")[-2]
    if len(agent.memory.get_all("reasoning")) > 0:
        local_memory.update(
            {
                "prev_reasoning_str": agent.memory.get_all("reasoning")[-1],
            }
        )
    if len(agent.memory.get_all("analysis")) > 0:
        local_memory.update(
            {
                "prev_analysis_str": agent.memory.get_all("analysis")[-1],
            }
        )
    if len(agent.memory.get_all("retrieved_memory")) > 0:
        latest_saved_memory_str = "\n".join(
            f"{idx}: {lmem}" for idx, lmem in enumerate(agent.memory.get_all("long_term_memory")[-agent.long_term_memory_len:], start=1)
        )
        if latest_saved_memory_str == "":
            latest_saved_memory_str = None
        local_memory.update(
            {
                "retrieved_memory_str": agent.memory.get_all("retrieved_memory")[-1],
                "latest_saved_memory_str": latest_saved_memory_str
            }
        )
    return local_memory

def agent_update_memory(agent, output: dict) -> None:
    for k, v in output.items():
        agent.memory.add(k, v)

def get_module_prompts(agent, obs_cond=False, system_prompt_filename="self_reflection_system", user_prompt_filename="self_reflection_user"):
    if obs_cond:
        if len(agent.memory.get_all("observation")) <= 1:
            return None, None
        assert (
            len(agent.memory.get_all("observation")) > 1
        ), "Need at least 2 observations for agent reflection"

    system_prompt = load_prompt(agent.prompt_path, system_prompt_filename).format(**agent.local_memory)
    user_prompt = load_prompt(agent.prompt_path, user_prompt_filename).format(**agent.local_memory)
    return system_prompt, user_prompt

def parse_module_response(response, module_type="self_reflection"):
    output = parse_semi_formatted_text(response, PREFIXS[module_type])
    return output

def agent_add_new_skill(agent, output):
    agent.skill_manager.add_new_skill( # FIXME: "last_action" & "last_action_name" should be delivered from the game_info
        skill_name=agent.local_memory.get("last_action_name", None), # from env
        skill=agent.local_memory.get("last_action", None), # from env
        description=output.get("skill_description", None) # from llm
    )

def agent_retrieve_skills(agent):
    return agent.skill_manager.retrieve_skills(agent.local_memory.get("knowledge", None)) # FIXME: "knowledge" prefix should be from knowledge_retrieval

def agent_add_new_long_term_memory(agent, output):
    memory_text = output.get("clue_extraction", "")
    memory_saving = output.get("saving", "No").lower() == "yes"
    if memory_text and memory_saving:
        agent.memory.add_long_term_memory(memory_text)

def agent_retrieve_long_term_memory(agent):
    return agent.memory.retrieve_long_term_memory(agent.local_memory.get("analysis", None))


if sys.platform == 'win32':
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

def set_log_path(cfg, expand_log_path: bool = True) -> omegaconf.omegaconf.DictConfig:
    if expand_log_path:
        log_path = os.path.join(
            cfg.log_path,
            cfg.env_name,
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        cfg.agent.log_path = log_path
        os.makedirs(log_path, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(cfg.log_path, 'agent_server.log')),
            logging.StreamHandler()
        ],
        force=True
    )

    return cfg

class MCPAgentServer:

    def __init__(self, mcp_server: FastMCP, config_path: str, expand_log_path: bool = True):
        self.cfg = self.create_config(config_path, expand_log_path)
        logger.info(f"config_path: {config_path}")
        self.mcp = mcp_server
        self.register_tools()

        # set agent
        self.agent_type = self.cfg.agent.agent_type
        self.prompt_path = self.cfg.agent.prompt_path
        self.agent_modules = AGENT_MODULES[self.agent_type]
        self.memory = GenericMemory(path=self.cfg.agent.log_path)
        self.skill_manager = SkillManager(path=self.cfg.agent.log_path)
        self.long_term_memory_len = self.cfg.agent.long_term_memory_len if hasattr(self.cfg.agent, "long_term_memory_len") else None

        # set temp var
        self.module_type = None

    def image2str(self, image):
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str

    def str2image(self, img_str):
        img_data = base64.b64decode(img_str)
        loaded_image = Image.open(BytesIO(img_data))
        image = loaded_image.copy()
        loaded_image.close()
        return image

    def create_config(self, config_path: str, expand_log_path: bool) -> omegaconf.omegaconf.DictConfig:
        cfg = omegaconf.OmegaConf.load(config_path)
        cfg = set_log_path(cfg, expand_log_path)
        return cfg

    def register_tools(self):
        @self.mcp.tool(name="list-agent-module-type", description="List the possible agent module type names.")
        def list_agent_module_type() -> str:
            return "The list of the possible agent module tpyes:\n" + "\n".join([module_type for module_type in self.agent_modules])

        @self.mcp.tool(name="add-observation-to-memory", description="Add a observation to the agent.")
        def add_observation_to_memory(obs_str: str, obs_image_str: str) -> str:
            self.memory.add("observation", obs_str)
            if obs_image_str!= "":
                obs_image = self.str2image(obs_image_str)
                self.memory.add("image", obs_image)
            return "Observation added"

        @self.mcp.tool(name="get-agent-module-prompts", description="Get an agent module named module_type and return its system and user prompts to response.")
        def get_agent_module_prompts(module_type: str, game_info: dict) -> str:
            #logger.info(f"[DEBUG] get_agent_module_prompts(), module_type: {self.module_type}")

            self.module_type = module_type
            self.local_memory = agent_get_local_memory(self, game_info)
            call_chat_completion = True
            if self.module_type == "action_inference":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "action_inference_system", "action_inference_user")
            elif self.module_type == "skill_management":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "skill_management_system", "skill_management_user")
                # add a new skill if the previous subtask succeeds
                # TODO: to handle general prefixs
                if not ("true" in str(self.local_memory.get("success", "")).lower()):
                    call_chat_completion = False
            elif self.module_type == "subtask_planning":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "subtask_planning_system", "subtask_planning_user")
            elif self.module_type == "knowledge_retrieval":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "knowledge_retrieval_system", "knowledge_retrieval_user")
            elif self.module_type == "self_reflection":
                system_prompt, user_prompt = get_module_prompts(
                    self, True, "self_reflection_system", "self_reflection_user")
            elif self.module_type == "long_term_management":
                system_prompt, user_prompt = get_module_prompts(
                    self, True, "long_term_system", "long_term_user")
            else:
                raise ValueError(f"Unknown module: {self.module_type}")
            
            image_strs = {k: self.image2str(self.local_memory[k]) for k in ("cur_image", "prev_image") if k in self.local_memory}
            
            return json.dumps({
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "image_strs": image_strs,
                "call_chat_completion": call_chat_completion
            })

        def _parse_module_response(response, module_type, structured_output_kwargs):
            if "guided_json" in structured_output_kwargs:
                output = json.loads(response)
                output = {key: value for key, value in output.items() if key in structured_output_kwargs["output_keys"]}
            else:
                output = parse_module_response(response, module_type)
            return output

        @self.mcp.tool(name="send-agent-module-response", description="Send a client response for the current agent module and return its parsed output.")
        def send_agent_module_response(response: str, structured_output_kwargs: dict) -> str:
            #logger.info(f"[DEBUG] send_agent_module_response(), module_type: {self.module_type}")

            if "\\n" in response:
                response = response.replace("\\n", "\n")
            if self.module_type == "action_inference":
                output = _parse_module_response(response, "action_inference", structured_output_kwargs)
                agent_update_memory(self, output)
                parsed_output = output.get("action", None)
            elif self.module_type == "skill_management":
                if response is not None:
                    output = _parse_module_response(response, "skill_management", structured_output_kwargs)
                    agent_update_memory(self, output)
                    agent_add_new_skill(self, output)
                skills_text = agent_retrieve_skills(self)
                output = {"retrieved_skills": skills_text}
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "subtask_planning":
                output = _parse_module_response(response, "subtask_planning", structured_output_kwargs)
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "knowledge_retrieval":
                output = _parse_module_response(response, "knowledge_retrieval", structured_output_kwargs)
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "self_reflection":
                output = _parse_module_response(response, "self_reflection", structured_output_kwargs)
                for key in PREFIXS["self_reflection"]:
                    if key not in output:
                        output[key] = None
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "long_term_management":
                output = _parse_module_response(response, "long_term_management", structured_output_kwargs)
                agent_update_memory(self, output)
                agent_add_new_long_term_memory(self, output)
                retrieved_memory = agent_retrieve_long_term_memory(self)
                output = {"retrieved_memory": retrieved_memory}
                agent_update_memory(self, output)
                parsed_output = output
            else:
                raise ValueError(f"Unknown module: {self.module_type}")
            return json.dumps({
                "parsed_output": str(parsed_output),
            })

    async def run(self):
        await self.mcp.run_stdio_async()
