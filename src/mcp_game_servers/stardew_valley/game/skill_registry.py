import ast
import base64
import inspect
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, AnyStr, Dict, Type

import dill
from dataclass_wizard import JSONWizard
from dataclass_wizard.abstractions import W
from dataclass_wizard.type_def import Encoder, JSONObject

from mcp_game_servers.gameio.io_env import IOEnvironment

logger = logging.getLogger(__name__)


@dataclass
class Skill(JSONWizard):

    skill_name: str
    skill_function: Any
    skill_code: str
    skill_code_base64: str

    def __call__(self, *args, **kwargs):
        return self.skill_function(*args, **kwargs)

    @classmethod
    def from_dict(cls: Type[W], o: JSONObject) -> W:
        skill_function = dill.loads(
            bytes.fromhex(o["skill_function"])
        )  # Load skill function from hex string

        return cls(
            skill_name=o["skill_name"],
            skill_function=skill_function,
            skill_code=o["skill_code"],
            skill_code_base64=o["skill_code_base64"],
        )

    def to_dict(self) -> JSONObject:
        skill_function_hex = dill.dumps(
            self.skill_function
        ).hex()  # Convert skill function to hex string

        return {
            "skill_name": self.skill_name,
            "skill_function": skill_function_hex,
            "skill_code": self.skill_code,
            "skill_code_base64": self.skill_code_base64,
        }

    def to_json(
        self: W, *, encoder: Encoder = json.dumps, **encoder_kwargs
    ) -> AnyStr:
        return json.dumps(self.to_dict(), **encoder_kwargs)

    @classmethod
    def from_json(
        cls: Type[W], s: AnyStr, *, decoder: Any = json.loads, **decoder_kwargs
    ) -> W:
        return cls.from_dict(json.loads(s, **decoder_kwargs))


SKILLS = {}


def register_skill(name):
    def decorator(skill):

        skill_name = name
        skill_function = skill
        skill_code = inspect.getsource(skill)

        # Remove unnecessary annotation in skill library
        if f'@register_skill("{name}")\n' in skill_code:
            skill_code = skill_code.replace(f'@register_skill("{name}")\n', "")

        skill_code_base64 = base64.b64encode(skill_code.encode("utf-8")).decode(
            "utf-8"
        )

        skill_ins = Skill(
            skill_name, skill_function, skill_code, skill_code_base64
        )
        SKILLS[skill_name] = skill_ins

        return skill_ins

    return decorator


class SkillRegistry:

    def __init__(self, config: Dict = None):
        self.skills = SKILLS
        self.skill_library = self.build_skill_library(config["skill_list"])
        self.io_env = IOEnvironment(config)

    def convert_expression_to_skill(self, expression: str = "open_map()"):
        try:
            parsed = ast.parse(expression, mode="eval")

            if isinstance(parsed.body, ast.Call):
                skill_name, skill_params = self.extract_function_info(
                    expression
                )
                return skill_name, skill_params
            elif isinstance(parsed.body, ast.List):

                skills_list = []
                for call in parsed.body.elts:
                    if isinstance(call, ast.Call):
                        call_str = ast.unparse(call).strip()
                        skill_name, skill_params = self.extract_function_info(
                            call_str
                        )
                        skills_list.append((skill_name, skill_params))
                    else:
                        raise ValueError(
                            "Input must be a list of function calls"
                        )
                return skills_list
            else:
                raise ValueError(
                    "Input must be a function call or a list of function calls"
                )

        except SyntaxError as e:
            raise ValueError(f"Error parsing input: {e}")

    def extract_function_info(self, input_string: str = "open_map()"):
        pattern = re.compile(r"(\w+)\((.*?)\)")
        match = pattern.match(input_string)

        if match:
            function_name = match.group(1)
            raw_arguments = match.group(2)

            # To avoid simple errors based on faulty model output
            if raw_arguments is not None and len(raw_arguments) > 0:
                raw_arguments = raw_arguments.replace(
                    "=false", "=False"
                ).replace("=true", "=True")

            try:
                parsed_arguments = ast.parse(
                    f"fake_func({raw_arguments})", mode="eval"
                )
            except SyntaxError:
                raise ValueError("Invalid function call/arg format to parse.")

            arguments = {"args": [], "kwargs": {}}
            for node in ast.walk(parsed_arguments):
                if isinstance(node, ast.Call):
                    for arg in node.args:
                        if isinstance(arg, ast.Constant):
                            arguments["args"].append(arg.value)
                        elif isinstance(arg, ast.Name):
                            arguments["args"].append(arg.id)
                    for kw in node.keywords:
                        arguments["kwargs"][kw.arg] = ast.literal_eval(kw.value)

            if len(raw_arguments) > 0 and len(arguments.keys()) == 0:
                raise ValueError("Call arguments not properly parsed!")

            return function_name, arguments

        else:
            raise ValueError("Invalid function call format string.")

    def build_skill_library(self, skill_list):
        skill_library = []

        for skill_name in self.skills:
            if skill_name in skill_list:
                skill_item = self.get_skill_description(skill_name)
                skill_library.append(skill_item)

        return skill_library

    def get_skill_description(
        self, skill_name: str, skill_library_with_code: bool = False
    ) -> Dict:

        skill = self.skills[skill_name]
        skill_function = skill.skill_function

        docstring = inspect.getdoc(skill_function)

        skill_code = ""
        for item in self.skills:
            if item == skill_name:
                skill_code = self.skills[item].skill_code
                break

        if docstring:
            params = inspect.signature(skill_function).parameters
            params = {k: v for k, v in params.items() if k != "io_env"}

            if len(params) > 0:
                param_descriptions = {}

                for param in params.values():
                    name = param.name
                    if name == "io_env":
                        continue
                    param_description = re.search(
                        rf"- {name}: (.+).", docstring
                    ).group(1)
                    param_descriptions[name] = param_description

                res = {
                    "function_expression": f"{skill_name}({', '.join(params.keys())})",
                    "description": docstring,
                    "parameters": param_descriptions,
                }
            else:
                res = {
                    "function_expression": f"{skill_name}()",
                    "description": docstring,
                    "parameters": {},
                }
        else:
            res = None

        if skill_library_with_code and res is not None:
            res["code"] = skill_code

        return res

    def execute_skill(
        self, skill_name: str = "open_map", skill_params: Dict = None
    ):
        try:
            if skill_name in self.skills:
                skill_function = self.skills[skill_name].skill_function
                skill_response = skill_function(
                    self.io_env, *skill_params["args"], **skill_params["kwargs"]
                )
            else:
                logger.warning(f"Function '{skill_name}' not found in the skill library.")
        except Exception as e:
            # logger.error(f"Error executing skill {skill_name}: {e}")
            logger.warning(f"Error executing skill {skill_name}: {e}")

        return None
