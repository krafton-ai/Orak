import sys
import os.path
import json
import time
import requests

from dataclasses import dataclass, field
from typing import SupportsFloat, Any, Tuple, Dict, Iterator, List

import gymnasium as gym
from gymnasium.core import ObsType

from mcp_game_servers.base_env import BaseEnv

from mcp_game_servers.minecraft.game.voyager.env.minecraft_launcher import MinecraftInstance
from mcp_game_servers.minecraft.game.voyager.env.process_monitor import SubprocessMonitor
import mcp_game_servers.minecraft.game.voyager.utils as U #FIXME: move to gaming_slm/utils

from mcp_game_servers.utils.types.game_io import Action, Obs
from mcp_game_servers.minecraft.game.voyager.control_primitives import load_control_primitives
from mcp_game_servers.minecraft.game.voyager.control_primitives_context import load_control_primitives_context

#gamingslm/src/mcp_game_servers/minecraft/game/voyager
#mcp_game_servers.minecraft.game.

import re
import time
from javascript import require

from PIL import Image

@dataclass
class MineCraftObs(Obs):
    events: dict
    chest_storage: dict
    image: Image.Image = None

    def to_text(self):
        chat_messages = []
        error_messages = []

        # FIXME: damage_messages is not used
        damage_messages = []
        assert self.events[-1][0] == "observe", "Last event must be observe"
        for i, (event_type, event) in enumerate(self.events):
            if event_type == "onChat":
                chat_messages.append(event["onChat"])
            elif event_type == "onError":
                error_messages.append(event["onError"])
            elif event_type == "onDamage":
                damage_messages.append(event["onDamage"])
            elif event_type == "observe":
                biome = event["status"]["biome"]
                time_of_day = event["status"]["timeOfDay"]
                voxels = event["voxels"]
                entities = event["status"]["entities"]
                health = event["status"]["health"]
                hunger = event["status"]["food"]
                position = event["status"]["position"]
                equipment = event["status"]["equipment"]
                inventory_used = event["status"]["inventoryUsed"]
                inventory = event["inventory"]
                assert i == len(self.events) - 1, "observe must be the last event"

        observation = ""

        observation += f"Biome: {biome}\n\n"

        observation += f"Time: {time_of_day}\n\n"

        if voxels:
            observation += f"Nearby blocks: {', '.join(voxels)}\n\n"
        else:
            observation += f"Nearby blocks: None\n\n"

        if entities:
            nearby_entities = [
                k for k, v in sorted(entities.items(), key=lambda x: x[1])
            ]
            observation += f"Nearby entities (nearest to farthest): {', '.join(nearby_entities)}\n\n"
        else:
            observation += f"Nearby entities (nearest to farthest): None\n\n"

        observation += f"Health: {health:.1f}/20\n\n"

        observation += f"Hunger: {hunger:.1f}/20\n\n"

        observation += f"Position: x={position['x']:.1f}, y={position['y']:.1f}, z={position['z']:.1f}\n\n"

        observation += f"Equipment: {equipment}\n\n"

        if inventory:
            observation += f"Inventory ({inventory_used}/36): {inventory}\n\n"
        else:
            observation += f"Inventory ({inventory_used}/36): Empty\n\n"

        chests = []
        for chest_position, chest in self.chest_storage.items():
            if isinstance(chest, dict) and len(chest) > 0:
                chests.append(f"{chest_position}: {chest}")
        for chest_position, chest in self.chest_storage.items():
            if isinstance(chest, dict) and len(chest) == 0:
                chests.append(f"{chest_position}: Empty")
        for chest_position, chest in self.chest_storage.items():
            if isinstance(chest, str):
                assert chest == "Unknown"
                chests.append(f"{chest_position}: Unknown items inside")
        assert len(chests) == len(self.chest_storage)

        if chests:
            chests = "\n".join(chests)
            chests =  f"Chests:\n{chests}\n\n"
        else:
            chests =  f"Chests: None\n\n"

        observation += chests

        return observation

    def evaluate(self, success_condition):
        for event_type, event in self.events:
            if event_type == "observe":
                equipment = event["status"]["equipment"]
                inventory = event["inventory"]

        if success_condition in equipment or success_condition in inventory:
            return True
        else:
            return False



@dataclass
class MineCraftAction(Action):
    values: Dict[str, str] = field(default_factory=dict)


class MinecraftEnv(BaseEnv):
    @dataclass
    class Config:
        task: str
        success_condition: str
        world_seed: int
        azure_login_path: str
        server_host: str
        server_port: int
        request_timeout: int
        logging: bool
        log_path: str
        input_modality: str = "text"

    cfg: Config

    def configure(self):
        self.task = self.cfg.task
        self.success_condition = self.cfg.success_condition
        self.world_seed = self.cfg.world_seed
        
        self.azure_login_path = self.cfg.azure_login_path #'keys/azure-login/azure_login.json'
        self.server_host = self.cfg.server_host
        self.server_port = self.cfg.server_port
        self.request_timeout = self.cfg.request_timeout

        self.logging = self.cfg.logging
        self.log_path = self.cfg.log_path

        # mineflayer variables
        with open(self.azure_login_path, 'r') as file:
            self.azure_login = json.load(file)

        self.mc_port = None
        self.server = f"{self.server_host}:{self.server_port}"
        self.mineflayer = self.get_mineflayer_process(self.server_port)
        self.mc_instance = self.get_mc_instance()

        self.has_reset = False
        self.reset_options = None
        self.connected = False
        self.server_paused = False

        self.env_wait_ticks = 20

        # game variables
        self.sub_task = self.task
        self.last_program = None
        self.last_program_name = None
        self.chest_storage = {}
        self.control_primitives = load_control_primitives()

    # mineflayer functions
    def get_mineflayer_process(self, server_port):
        file_path = os.path.abspath(os.path.dirname(__file__))
        return SubprocessMonitor(
            commands=[
                "node",
                U.f_join(file_path, "voyager/env/mineflayer/index.js"),
                str(server_port),
            ],
            name="mineflayer",
            ready_match=r"Server started on port (\d+)",
            log_path=self.log_path,
        )

    def get_mc_instance(self):
        print("Creating Minecraft server")
        return MinecraftInstance(
            **self.azure_login,
            mineflayer=self.mineflayer,
            log_path=self.log_path,
        )

    def check_process(self):
        if self.mc_instance and not self.mc_instance.is_running:
            # if self.mc_instance:
            #     self.mc_instance.check_process()
            #     if not self.mc_instance.is_running:
            print("Starting Minecraft server")
            self.mc_instance.run()
            self.mc_port = self.mc_instance.port
            self.reset_options["port"] = self.mc_instance.port
            print(f"Server started on port {self.reset_options['port']}")
        retry = 0
        while not self.mineflayer.is_running:
            print("Mineflayer process has exited, restarting")
            self.mineflayer.run()
            if not self.mineflayer.is_running:
                if retry > 3:
                    raise RuntimeError("Mineflayer process failed to start")
                else:
                    continue
            res = requests.post(
                f"{self.server}/start",
                json=self.reset_options,
                timeout=self.request_timeout,
            )
            if res.status_code != 200:
                self.mineflayer.stop()
                raise RuntimeError(
                    f"Minecraft server reply with code {res.status_code}"
                )
            return res.json()

    def pause(self):
        if self.mineflayer.is_running and not self.server_paused:
            res = requests.post(f"{self.server}/pause")
            if res.status_code == 200:
                self.server_paused = True
        return self.server_paused

    def unpause(self):
        if self.mineflayer.is_running and self.server_paused:
            res = requests.post(f"{self.server}/pause")
            if res.status_code == 200:
                self.server_paused = False
            else:
                print(res.json())
        return self.server_paused

    def reset(
        self,
        *,
        seed=None,
        options=None,
    ) -> Tuple[ObsType, Dict[str, Any]]:
        if options is None:
            options = {}

        if options.get("inventory", {}) and options.get("mode", "hard") != "hard":
            raise RuntimeError("inventory can only be set when options is hard")

        self.reset_options = {
            "port": self.mc_port,
            "reset": options.get("mode", "hard"),
            "inventory": options.get("inventory", {}),
            "equipment": options.get("equipment", []),
            "spread": options.get("spread", False),
            "waitTicks": options.get("wait_ticks", 5),
            "position": options.get("position", None),
        }
        self.unpause()
        self.mineflayer.stop()
        time.sleep(1)  # wait for mineflayer to exit

        returned_data = self.check_process()
        self.has_reset = True
        self.connected = True
        # All the reset in step will be soft
        self.reset_options["reset"] = "soft"
        self.pause()
        return json.loads(returned_data)

    def close(self):
        self.unpause()
        if self.connected:
            res = requests.post(f"{self.server}/stop")
            if res.status_code == 200:
                self.connected = False
        if self.mc_instance:
            self.mc_instance.stop()
        self.mineflayer.stop()
        return not self.connected
    
    # gamebench functions
    def update_chest_storage(self, chests):
        for position, chest in chests.items():
            if position in self.chest_storage:
                if isinstance(chest, dict):
                    self.chest_storage[position] = chest
                if chest == "Invalid":
                    self.chest_storage.pop(position)
            else:
                if chest != "Invalid":
                    self.chest_storage[position] = chest

    def initial_obs(self) -> Obs:
        self.reset(
            options={
                "mode": "soft",
                "wait_ticks": self.env_wait_ticks,
            }
        )
        difficulty = "peaceful"
        x, y, z = 604, 100, -823 # world_seed: 
        self.events = self.execute(
            "bot.chat(`/time set ${getNextTime()}`);\n"
            + f"bot.chat('/difficulty {difficulty}');\n"
            + f"bot.chat('/tp @a {x} {y} {z}');\n" # initial position
        )

        obs = MineCraftObs(
            events=self.events,
            chest_storage=self.chest_storage,
        )
        return obs

    def get_game_info(self) -> dict:
        chat_messages, error_messages = [], []
        assert self.events[-1][0] == "observe", "Last event must be observe"
        for i, (event_type, event) in enumerate(self.events):
            if event_type == "onChat":
                chat_messages.append(event["onChat"])
            elif event_type == "onError":
                error_messages.append(event["onError"])
        if error_messages:
            error = "\n".join(error_messages)
        else:
            error = "No error"
        if chat_messages:
            chat_log = "\n".join(chat_messages)
        else:
            chat_log = "None"

        # skills
        base_skills = [
            "exploreUntil",
            "mineBlock",
            "craftItem",
            "placeItem",
            "smeltItem",
            "killMob",
            "useChest",
            "mineflayer",
        ]
        programs_skill = "\n\n".join(load_control_primitives_context(base_skills))

        return {
            "game_name": "MineCraft",
            "final_task": self.task,
            "subtask": self.task,
            "last_action": self.last_program,
            "last_action_name": self.last_program_name, 
            "error": error, 
            "chat_log": chat_log,
            "base_skills": programs_skill,
            "retrieved_skills": ""
        }

    def obs2text(self, obs: Obs) -> str:
        text = obs.to_text()
        return text

    def text2action(self, text: str) -> MineCraftAction:
        retry = 3
        error = None

        while retry > 0:
            try:
                babel = require("@babel/core")
                babel_generator = require("@babel/generator").default

                code_pattern = re.compile(r"```(?:javascript|js)(.*?)```", re.DOTALL)
                code = "\n".join(code_pattern.findall(text))
                parsed = babel.parse(code)
                functions = []
                assert len(list(parsed.program.body)) > 0, "No functions found"
                for i, node in enumerate(parsed.program.body):
                    if node.type != "FunctionDeclaration":
                        continue
                    node_type = (
                        "AsyncFunctionDeclaration"
                        if node["async"]
                        else "FunctionDeclaration"
                    )
                    functions.append(
                        {
                            "name": node.id.name,
                            "type": node_type,
                            "body": babel_generator(node).code,
                            "params": list(node["params"]),
                        }
                    )
                # find the last async function
                main_function = None
                for function in reversed(functions):
                    if function["type"] == "AsyncFunctionDeclaration":
                        main_function = function
                        break
                assert (
                    main_function is not None
                ), "No async function found. Your main function must be async."
                assert (
                    len(main_function["params"]) == 1
                    and main_function["params"][0].name == "bot"
                ), f"Main function {main_function['name']} must take a single argument named 'bot'"
                program_code = "\n\n".join(function["body"] for function in functions)
                exec_code = f"await {main_function['name']}(bot);"
                
                actions = {
                    "program_code": program_code,
                    "program_name": main_function["name"],
                    "exec_code": exec_code,
                }
                return MineCraftAction(values=actions)
            except Exception as e:
                retry -= 1
                error = e
                time.sleep(1)
        return MineCraftAction(values={"error": f"Error parsing action response (before program execution): {error}"})
    
    def execute(
        self,
        code: str,
        programs: str = "",
    ) -> Tuple[ObsType, SupportsFloat, bool, bool, Dict[str, Any]]:
        if not self.has_reset:
            raise RuntimeError("Environment has not been reset yet")
        self.check_process()
        self.unpause()
        data = {
            "code": code,
            "programs": programs,
        }
        res = requests.post(
            f"{self.server}/step", json=data, timeout=self.request_timeout
        )
        if res.status_code != 200:
            raise RuntimeError("Failed to step Minecraft server")
        returned_data = res.json()
        self.pause()
        return json.loads(returned_data)


    def step(
        self, actions: MineCraftAction
    ) -> Tuple[ObsType, SupportsFloat, bool, bool, Dict[str, Any]]:
        
        try:
            code = actions.values["program_code"] + "\n" + actions.values["exec_code"]
            programs = ""
            for primitives in self.control_primitives:
                programs += f"{primitives}\n\n"
            # add retrieved_skills
            skill_path = f"data/skills/{self.log_path.replace('logs/', '', 1)}/retrieved_skills.txt"
            if os.path.exists(skill_path):
                with open(skill_path, 'r') as file:
                    retrieved_skills = file.read()
                    programs += f"{retrieved_skills}\n\n"

            self.events = self.execute(code, programs)

            # env logging
            self.last_program = actions.values["program_code"]
            self.last_program_name = actions.values["program_code"]
            self.update_chest_storage(self.events[-1][1]["nearbyChests"])
        except:
            print("Action is not proper dictionary, Try again!")
            print(f"{actions.values} ")

        obs = MineCraftObs(
            events=self.events,
            chest_storage=self.chest_storage,
        )
        return obs, 0, False, False, {}

    def evaluate(self, obs: MineCraftObs):
        if obs.evaluate(self.success_condition):
            self.close()
            return 1, True
        else:
            return 0, False 