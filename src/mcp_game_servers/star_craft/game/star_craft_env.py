import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, List, Optional
import multiprocessing
from PIL import Image
from collections import deque
import numpy as np
import re
from dacite import from_dict

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.gameio.window_capture import WindowCapture
from mcp_game_servers.utils.types.game_io import Action, Obs

from .utils.bots import sc2_run_game
from .utils.actions import ActionDescriptions

LADDER_MAP_2023 = [
    'Altitude LE',
    'Ancient Cistern LE',
    'Babylon LE',
    'Dragon Scales LE',
    'Gresvan LE',
    'Neohumanity LE',
    'Royal Blood LE'
]

def wait_for_window(window_name: str, timeout: int = 30, interval: float = 1.0) -> WindowCapture:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            wc = WindowCapture(window_name, adjust_dpi=True)
            return wc
        except Exception as e:
            print(f"[INFO] Waiting for window '{window_name}'... ({e})")
            time.sleep(interval)
    raise TimeoutError(f"Window '{window_name}' not found within {timeout} seconds.")

@dataclass
class StarCraftObs(Obs):
    observation: dict
    image: Optional[Image.Image] = None

    def to_text(self):

        def create_summary(category_data):
            summary = ""
            for key, value in category_data.items():
                if isinstance(value, dict):
                    sub_summary = create_summary(value)
                    if sub_summary != "":
                        summary += f"\n{key.replace('_', ' ').capitalize()}:\n{sub_summary}"
                elif value != 0: 
                    summary += f"- {key.replace('_', ' ').capitalize()}: {value}\n"
            return summary
        
        for key in self.observation:
            if isinstance(self.observation[key], str):
                try:
                    self.observation[key] = json.loads(self.observation[key].replace("'", "\""))
                except json.JSONDecodeError:
                    raise ValueError(f"Failed to parse value of '{key}' as JSON. Value: {self.observation[key]}")

        summary = ""

        for key in self.observation:

            temp_obs = self.observation[key]

            if not isinstance(temp_obs.get('resource'), dict):
                raise ValueError(f"Expected 'resource' to be a dictionary, but got: {type(temp_obs.get('resource'))}, value: {temp_obs.get('resource')}")

            game_time = temp_obs['resource'].get('game_time', "unknown time")

            temp_summary = f"{key}: At {game_time} game time, our current StarCraft II situation is as follows:\n\n"

            categories = [
                ("Resources", temp_obs.get("resource", {})),
                ("Buildings", temp_obs.get("building", {})),
                ("Units", temp_obs.get("unit", {})),
                ("Research", temp_obs.get("research", {})),
                ("In Progress", temp_obs.get("in_progress", {})),
                ("Enemy", temp_obs.get("enemy", {})),
            ]

            for category, category_data in categories:
                category_summary = create_summary(category_data)
                if category_summary != "":
                    temp_summary += f"{category}:\n{category_summary}\n"
            
            summary += temp_summary

        return summary

@dataclass
class StarCraftAction(Action):
    actions: List[str] = field(default_factory=list)

    def __iter__(self) -> Iterator[str]:
        return iter(self.actions)

    def __getitem__(self, index: int) -> int:
        return self.actions[index]

    def __len__(self) -> int:
        return len(self.actions)

    def to_json(self) -> str:
        return json.dumps(self.actions)


class StarCraftEnv(BaseEnv):
    @dataclass
    class Config:
        task: str

        map_idx: int
        player_race: str

        bot_race: str
        bot_difficulty: int
        bot_build: int

        query_interval: int
        num_summaries: int
        num_actions: int
        
        log_path: str

        input_modality: str = "text"

    cfg: Config
    
    def configure(self):
        self.process_id = -1
        self.log_path = self.cfg.log_path

        self.map_pool = LADDER_MAP_2023
        self.map_idx = self.cfg.map_idx
        self.map_name = self.map_pool[self.map_idx]
        
        self.player_race = self.cfg.player_race

        self.bot_race = self.cfg.bot_race
        self.bot_difficulty = self.cfg.bot_difficulty
        self.bot_build = self.cfg.bot_build
        
        self.action_description = ActionDescriptions(self.player_race)
        self.action_dict_tmp = self.action_description.action_descriptions
        self.action_dict = {}
        for category in self.action_dict_tmp:
            for key, value in self.action_dict_tmp[category].items():
                self.action_dict[value.upper()] = key
        print("action_dict", self.action_dict)

        self.query_interval = self.cfg.query_interval
        self.num_summaries = self.cfg.num_summaries
        self.num_actions = self.cfg.num_actions

        self.summary = {}
        self.executed_actions = []

        self.lock = multiprocessing.Manager().Lock()
        self.transaction = multiprocessing.Manager().dict()
        self.transaction.update(
            {'information': {}, 'reward': 0, 'action': None,
             'done': False, 'result': None, 'iter': 0, 'command': None, "output_command_flag": False,
             'action_executed': [], 'action_failures': [], })
        self.isReadyForNextStep = multiprocessing.Event()
        self.game_end_event = multiprocessing.Event()
        self.game_over = multiprocessing.Value('b', False)
        self.done_event = multiprocessing.Event()
        self.p = None
        self.check_process(reset=True)
        self.check_process()

        self.use_image = self.cfg.input_modality in ["image", "text_image"]
        if self.use_image:
            self.window_capture = wait_for_window("StarCraft II", timeout=60)

    def check_process(self, reset=False):
        if self.p is not None:
            if self.p.is_alive():
                if not self.game_over.value:  # Check if the game is over
                    return  # If the game is not over, just return and do not restart the process
                self.p.terminate()
            self.p.join()
        if reset:
            self.transaction.update(
                {'information': {}, 'reward': 0, 'action': None,
                 'done': False, 'result': None, 'iter': 0, 'command': None, "output_command_flag": False,
                 'action_executed': [], 'action_failures': [], })
            self.game_end_event.clear()  # Clear the game_end_event
            if self.player_race == 'Protoss':
                self.p = multiprocessing.Process(target=sc2_run_game, args=(
                    self.transaction, self.lock, self.isReadyForNextStep, self.game_end_event,
                    self.done_event, self.bot_race, self.bot_difficulty, self.bot_build, self.map_name, self.log_path))
            else:
                raise ValueError("Invalid race. Only 'Protoss' and 'Zerg' are supported.")
            self.p.start()

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        self.check_process(reset=True)
        self.game_end_event.clear()

        image = None
        if self.use_image:
            try:
                image = self.window_capture.capture(log_path=self.cfg.log_path)
            except Exception as e:
                print(f"[WARNING] Failed to capture image: {e}")
                image = None
            
        state = from_dict(StarCraftObs, {'observation': self.transaction['information'], 'image': image})

        return state

    def initial_obs(self) -> Obs:
        return self.reset()

    def obs2text(self, obs: Obs) -> str:
        if not obs.observation:
            return None
        else:
            return obs.to_text()

    def text2action(self, text: str) -> Action:

        individual_actions_pattern = r"\d+: <?([^>\n]+)>?"
        actions = re.findall(individual_actions_pattern, text)

        valid_actions = []

        for action in actions:
            action = action.upper()
            if action in self.action_dict:
                valid_actions.append(action)

        if len(valid_actions) > self.num_actions:
            valid_actions = valid_actions[:self.num_actions]
        elif len(valid_actions) < self.num_actions:
            for _ in range(self.num_actions - len(valid_actions)):
                valid_actions.append("EMPTY ACTION")
        
        final_actions = []

        for i in range(self.query_interval):
            if i % 2 == 0:
                final_actions.append(valid_actions.pop(0))
            else:
                final_actions.append("EMPTY ACTION")

        return StarCraftAction(actions=final_actions)
    
    def action_step(self, action) -> tuple[Obs, float, bool, bool, dict[str, Any]]:

        with self.lock:
            self.transaction['action'] = action

        while not (self.done_event.is_set() or self.isReadyForNextStep.is_set()):
            time.sleep(0.0001)

        if self.done_event.is_set():
            self.done_event.clear()
            self.isReadyForNextStep.clear()
            self.game_over.value = True
            if self.transaction['result'].name == 'Victory':
                self.transaction['reward'] += 50
        elif self.isReadyForNextStep.is_set():
            self.isReadyForNextStep.clear()
            self.check_process()
        state = self.transaction['information']

        return state, self.transaction['done']

    def step(self, action: Action) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        
        self.summary = {}
        self.executed_actions = []

        for i in range(self.query_interval):
            curr_action = self.action_dict[action.actions[i]]
            obs, done = self.action_step(curr_action)
            self.executed_actions.append(self.transaction['action_executed'])

            if done:
                break
            if i >= self.query_interval - self.num_summaries:
                summary_idx = i - self.query_interval + self.num_summaries + 1
                self.summary[f'Summary {summary_idx}'] = obs

        image = None
        if self.use_image:
            image = self.window_capture.capture(log_path=self.cfg.log_path)
            
        state = from_dict(StarCraftObs, {'observation': self.summary, 'image': image})

        return state, 0, done, False, None

    def evaluate(self, obs: Obs):
        result = self.transaction['result']
        return result.name if result is not None else None, self.transaction['done']

    def get_game_info(self) -> dict:
        return {
            "player_race": self.player_race,
            "enemy_race": self.bot_race,
            "action_executed": self.executed_actions,
            "action_dict": self.action_dict,
            "num_actions": self.num_actions,
        }