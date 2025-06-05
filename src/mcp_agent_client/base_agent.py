import importlib
import os
import json
from dataclasses import dataclass, field
from typing import Dict, Optional, Union, Any

from omegaconf import DictConfig

from mcp_agent_client.llms.llm import load_model, LocalBase
from mcp_agent_client.llms.openai_utils import (
    Logger,
    MoneyManager,
    pretty_print_conversation,
)
from mcp_agent_client.json_schemas import SCHEMA_REGISTRY

from mcp_game_servers.utils.types.misc import Configurable

from mcp_agent_servers.base_server import (
    PREFIXS,
    AGENT_MODULES,
    GenericMemory,
    SkillManager,
    agent_get_local_memory,
    get_module_prompts,
    parse_module_response,
    agent_update_memory,
    agent_add_new_long_term_memory,
    agent_retrieve_long_term_memory,
    agent_add_new_skill,
    agent_retrieve_skills
)

from PIL import Image
from io import BytesIO
import re
import base64

# Function to encode PIL.Image.Image to base64
def encode_image(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

class BaseAgent(Configurable):
    @dataclass
    class Config:
        llm_name: str
        temperature: float = 0.0
        repetition_penalty: float = 0.0
        api_key: str = ""
        api_base_url: str = ""

        agent_type: str = "zeroshot_agent"
        prompt_path: str = ""

        log_path: str = "./logs"
        debug_mode: bool = False
        structured_output: Optional[Dict[str, str]] = field(default_factory=dict)
        long_term_memory_len: int = 10

    cfg: Config  # add this to every subclass to enable static type checking

    def configure(self):
        pass

    def __init__(
        self, cfg: Optional[Union[dict, DictConfig]] = None, *args, **kwargs
    ) -> None:
        super().__init__(cfg, *args, **kwargs)

        # default arguments
        self.orig_model = self.cfg.llm_name
        self.temperature = self.cfg.temperature
        self.repetition_penalty = self.cfg.repetition_penalty
        self.api_key = self.cfg.api_key
        self.api_base_url = self.cfg.api_base_url

        self.log_path = self.cfg.log_path
        self.debug_mode = self.cfg.debug_mode

        self.agent_type = self.cfg.agent_type
        self.agent_modules = AGENT_MODULES[self.agent_type]
        self.structured_output = self.cfg.structured_output

        self._setup_model()
        self._setup_logger()

    def _setup_model(self):
        loaded_model = load_model(
            self.orig_model,
            temperature=self.temperature,
            repetition_penalty=self.repetition_penalty,
            api_key=self.api_key,
            api_base_url=self.api_base_url
        )

        self.model_name = loaded_model["model_name"]
        self.ctx_manager: MoneyManager = loaded_model["ctx_manager"]
        self.llm = loaded_model["llm"]
        self.tokenizer = loaded_model["tokenizer"]

    def _setup_logger(self):
        self.logger = Logger(log_path=self.log_path)

    def chat_completion(self, system_prompt, user_prompt, images={}, **kwargs):
        messages = []

        messages.append({"role": "system", "content": system_prompt})

        if images:
            pattern = r"(<\|cur_state_image\|>|<\|prev_state_image\|>)"
            parts = re.split(pattern, user_prompt)

            user_prompt = []
            for part in parts:
                if part == "<|cur_state_image|>":
                    if "cur_image" not in images:
                        user_prompt.append(
                            {
                                "type": "text",
                                "text": "None",
                            }
                        )
                        continue
                    base64_image = encode_image(images["cur_image"])
                    user_prompt.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                            }
                        }
                    )
                elif part == "<|prev_state_image|>":
                    if "prev_image" not in images:
                        user_prompt.append(
                            {
                                "type": "text",
                                "text": "None",
                            }
                        )
                        continue
                    base64_image = encode_image(images["prev_image"])
                    user_prompt.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                            }
                        }
                    )
                else:
                    user_prompt.append(
                        {
                            "type": "text",
                            "text": part,
                        }
                    )

        messages.append({"role": "user", "content": user_prompt})

        output = self.llm(messages, **kwargs)

        messages.append(
            {
                "content": output["response"].choices[0].message.content,
                "role": output["response"].choices[0].message.role,
            }
        )
        messages.append({"total_cost": self.ctx_manager.total_cost})

        if self.debug_mode:
            pretty_print_conversation(messages)
        self.logger(messages)

        completion = output["response"].choices[0].message.content
        return completion

    def update_parameters(
        self,
        temperature: float | None = None,
        repetition_penalty: float | None = None,
    ) -> None:
        if temperature is not None:
            self.temperature = temperature
        if repetition_penalty is not None:
            self.repetition_penalty = repetition_penalty
        self._setup_model()

    # Return the total cost for calling this agent
    def total_cost(self) -> float:
        return self.ctx_manager.total_cost

    def refresh(self) -> None:
        return self.ctx_manager.refresh()

class BaselineAgent(BaseAgent):
    @dataclass
    class Config:
        llm_name: str
        temperature: float = 0.0
        repetition_penalty: float = 0.0
        api_key: str = ""
        api_base_url: str = ""

        agent_type: str = "zeroshot_agent"
        prompt_path: str = ""

        log_path: str = "./logs"
        debug_mode: bool = False
        structured_output: Optional[Dict[str, str]] = field(default_factory=dict)
        long_term_memory_len: int = 10

    cfg: Config

    def configure(self):
        self.prompt_path = self.cfg.prompt_path
        self.long_term_memory_len = self.cfg.long_term_memory_len

        self.memory = GenericMemory(path=self.cfg.log_path)
        self.skill_manager = SkillManager(path=self.cfg.log_path)
        
        self.modality = self.cfg.prompt_path.split('.')[-1]
        self.agent_type = self.cfg.agent_type
        
        # Pokemon specific setup
        self.process_state = 'pokemon' in self.agent_type
        if self.process_state:
            try:
                from mcp_game_servers.pokemon_red.game.utils.pokemon_tools import PokemonToolset
                self.toolset = PokemonToolset(self)
            except ImportError:
                print("Pokemon tools not available")
                self.toolset = None
        else:
            self.toolset = None
            
        self.last_module = ""

    def set_env_interface(self, env):
        self.env = env

    def module2func(self, module):
        if module == "action_inference":
            return self.action_inference
        elif module == "skill_management":
            return self.skill_management
        elif module == "subtask_planning":
            return self.subtask_planning
        elif module == "knowledge_retrieval":
            return self.knowledge_retrieval
        elif module == "self_reflection":
            return self.self_reflection
        elif module == "long_term_management":
            return self.long_term_management
        elif module == "history_summarization":
            return self.history_summarization
        elif module == "memory_management":
            return self.memory_management
        elif module == "action_execution":
            return self.action_execution
        raise ValueError(f"Unknown module: {module}")

    def __call__(self, obs, game_info: Optional[dict] = None) -> str:
        text_obs, image_obs = obs.to_text(), getattr(obs, 'image', None)

        if self.process_state and self.toolset is not None:
            try:
                from mcp_game_servers.pokemon_red.game.utils.pokemon_tools import process_state_tool
                text_obs, self.memory.state_dict, self.memory.map_memory_dict, self.memory.step_count, self.memory.dialog_buffer = process_state_tool(
                    self.env, self.toolset, self.memory.map_memory_dict,
                    self.memory.step_count, self.memory.dialog_buffer, text_obs,
                )
                obs.set_text(text_obs)
            except ImportError:
                print("Pokemon process_state_tool not available")

        # Update observation to memory
        self.memory.add("observation", text_obs)
        if image_obs is not None:
            self.memory.add("image", image_obs)

        for module in self.agent_modules:
            self.local_memory = agent_get_local_memory(self, game_info)

            structured_output_kwargs = {}
            if module in self.structured_output:
                assert isinstance(self.llm, LocalBase), "Structured output is currently tested for local models."

                if "guided_regex" in self.structured_output[module]:
                    structured_output_kwargs.update(self.structured_output[module])
                elif "guided_json" in self.structured_output[module]:
                    json_schema = SCHEMA_REGISTRY[self.structured_output[module]["guided_json"]]
                    structured_output_kwargs.update({"guided_json": json_schema})
                    structured_output_kwargs.update({"output_keys": self.structured_output[module]["output_keys"]})

            action = self.module2func(module)(**structured_output_kwargs)
            self.last_module = module

        return str(action)

    def self_reflection(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
            self, True, "self_reflection_system", "self_reflection_user")
        if system_prompt is None and user_prompt is None:
            return

        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "self_reflection")
        
        for key in PREFIXS["self_reflection"]:
            if key not in output:
                output[key] = None

        agent_update_memory(self, output)

        return output

    def subtask_planning(self, **kwargs):
        
        system_prompt, user_prompt = get_module_prompts(
            self, False, "subtask_planning_system", "subtask_planning_user")

        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "subtask_planning")

        agent_update_memory(self, output)

        return output
    
    def knowledge_retrieval(self, **kwargs):
        
        system_prompt, user_prompt = get_module_prompts(
            self, False, "knowledge_retrieval_system", "knowledge_retrieval_user")

        response = self.chat_completion(system_prompt, user_prompt)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "knowledge_retrieval")

        agent_update_memory(self, output)

        return output

    def skill_management(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
                self, True, "skill_management_system", "skill_management_user")
        if system_prompt is None and user_prompt is None:
            return

        # add new skills if the "previous" subtask succeeds
        # TODO: to handle general prefixs
        if "true" in str(self.local_memory.get("success", "")).lower(): # FIXME: "success" prefix should be from self_reflection
            response = self.chat_completion(system_prompt, user_prompt)
            output = parse_module_response(response, "skill_management")
            agent_update_memory(self, output)

            agent_add_new_skill(self, output)

        # retrieve skills based on the "current" subtask
        skills_text = agent_retrieve_skills(self) # FIXME: "knowledge" prefix should be from knowledge_retrieval
        output = {"retrieved_skills": skills_text}

        agent_update_memory(self, output)

        return output

    def long_term_management(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
                self, True, "long_term_system", "long_term_user")
        if system_prompt is None and user_prompt is None:
            return

        response = self.chat_completion(system_prompt, user_prompt)
        output = parse_module_response(response, "long_term_management")
        agent_update_memory(self, output)

        agent_add_new_long_term_memory(self, output)

        retrieved_memory = agent_retrieve_long_term_memory(self)
        output = {"retrieved_memory": retrieved_memory}
        agent_update_memory(self, output)

        return output

    def action_inference(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
                self, False, "action_inference_system", "action_inference_user")
        
        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "action_inference")

        agent_update_memory(self, output)

        return output.get("action", None)
    
    def history_summarization(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
                self, True, "history_summarization_system", "history_summarization_user")
        if system_prompt is None and user_prompt is None:
            return

        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "history_summarization")
        
        for key in PREFIXS["history_summarization"]:
            if key not in output:
                output[key] = None

        action_memory = self.memory.get_all('action')
        output['short_term_summary'] += f"\nExecuted Action Sequence: (oldest)[{'->'.join(map(str, action_memory[-self.memory.num_action_buffer:]))}](latest)" if action_memory else None

        agent_update_memory(self, output)

        return output
    
    def memory_management(self, **kwargs):
        print('Memory Managing...')
        goal = self.memory.get_last('subtask_decription')
        query = None
        
        # default environment_perception
        state_dict = self.memory.state_dict
        cur_state = state_dict['state']
        if cur_state == 'Title':
            self.memory.environment_perception = f"State:{cur_state}"
        elif cur_state == 'Field':
            map_info = state_dict['map_info']
            self.memory.environment_perception = f"State:{cur_state}, MapName:{map_info['map_name']}, PlayerPos:({map_info['player_pos_x']},{map_info['player_pos_y']})"
        elif cur_state == 'Dialog':
            self.memory.environment_perception = f"State:{cur_state}, ScreenText:{state_dict['filtered_screen_text']}"
        else:
            self.memory.environment_perception = f"State:{cur_state}, Enemy:{state_dict['enemy_pokemon']}, Party:{state_dict['your_party']}"

        if self.memory.is_exist('self_reflection'):
            try:
                reflection_data_str = self.memory.get_last('self_reflection').strip()
                json_str = re.sub(r"^```json\s*|\s*```$", "", reflection_data_str, flags=re.DOTALL)
                reflection_json = json.loads(json_str)

                if 'Goal' in reflection_json:
                    goal = str(reflection_json['Goal'])
                else:
                    goal = 'Not Provided from reflection'

            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                print(f"Error processing self_reflection: {e}")
                print("Use default goal and environment_perception.")
            
            if 'self_reflection' == self.last_module:  # LTM Managing
                try:
                    # Lazy import pokemon tools only when needed
                    from mcp_game_servers.pokemon_red.game.utils.memory_manager import extract_memory_entries
                    memory_entries = extract_memory_entries(self.memory.get_last('self_reflection'))
                
                    for entry in memory_entries:
                        self.memory.add_long_term_memory(entry, similarity_threshold=0.2)
                except ImportError:
                    print("Pokemon Red tools not available")
                    pass
            else:
                goal = self.memory.get_last('subtask_decription')

        try:
            # Lazy import pokemon tools only when needed
            from mcp_game_servers.pokemon_red.game.utils.memory_manager import build_memory_query
            query = build_memory_query(goal, self.memory.environment_perception)
        except ImportError:
            print("Pokemon Red tools not available")
            query = None

        if query is None:
            print("Query could not be built.")

        memory_snippets = self.memory.retrieve_long_term_memory(query, similarity_threshold=0.4)

        self.memory.add('relevant_memory', memory_snippets or None)

        return self.memory.get_last('relevant_memory')
    
    def action_execution(self, **kwargs):
        action_response = self.memory.get_last('action')
        action_response = action_response.split('\n')[0]
        actions = [part.strip() for part in re.split(r'\s*(\||\n)\s*', action_response) if part.strip() and part.strip() not in ('|', '\n')]
        actions = actions[:5]
        messages = []
        flag = ''
        
        try:
            from mcp_game_servers.pokemon_red.game.utils.pokemon_tools import execute_action_response
            has_pokemon_tools = True
        except ImportError:
            print("Pokemon execute_action_response not available")
            has_pokemon_tools = False
            
        for action_idx, action in enumerate(actions):
            if action_idx==0:
                if 'use_tool' in action and has_pokemon_tools:
                    messages.append(f"{action}\n(isSuccess,Feedback):{execute_action_response(self.toolset, action)}")
                    flag = 'use_tool'
                else:
                    messages.append(action)
                    flag = 'low'
            else:
                if flag == 'use_tool':
                    if 'use_tool' in action and has_pokemon_tools:
                        messages.append(f"{action}\n(isSuccess,Feedback):{execute_action_response(self.toolset, action)}")
                    else:
                        break
                else:
                    if 'use_tool' in action:
                        break
                    else:
                        messages.append(action)
        final_action = "|".join(messages)
        self.memory.add('action', final_action)

        # Managing History
        data = {
            f"{self.memory.step_count}th_state": self.memory.environment_perception,
            f"{self.memory.step_count}th_action": self.memory.get_last('action'),
        }
        self.memory.histories.append(data)
        self.memory.histories = self.memory.histories[-self.memory.num_history_buffer:]
        self.memory.add('short_term_history', self.memory.histories)

        # update long-term memory
        lessons = self.memory.get_last('lessons_learned')
        if lessons and lessons != "Not Provided":
            lessons_list = lessons.split('\n')
            for lesson in lessons_list:
                lesson = lesson.strip()
                lesson_match = re.match(r"^\s*[-*]\s*(.*)", lesson)
                if lesson_match:
                    lesson_text = lesson_match.group(1).strip()
                    if lesson_text:
                        self.memory.add_long_term_memory(lesson_text, similarity_threshold=0.2)
                elif lesson:
                    self.memory.add_long_term_memory(lesson, similarity_threshold=0.2)

        return final_action
