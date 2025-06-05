import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, List, Optional
import multiprocessing
from collections import deque
import numpy as np
import re
from dacite import from_dict

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.utils.types.game_io import Action, Obs

from ...star_craft.game.utils.bots import sc2_run_multi_game
from ...star_craft.game.utils.actions import ActionDescriptions

LADDER_MAP_2023 = [
    'Altitude LE',
    'Ancient Cistern LE',
    'Babylon LE',
    'Dragon Scales LE',
    'Gresvan LE',
    'Neohumanity LE',
    'Royal Blood LE'
]

@dataclass
class StarCraftObs(Obs):
    observation: dict

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

            temp_summary = f"At {game_time} game time, our current StarCraft II situation is as follows:\n\n"

            categories = [
                ("Resources", temp_obs.get("resource", {})),
                ("Buildings", temp_obs.get("building", {})),
                ("Units", temp_obs.get("unit", {})),
                ("Research", temp_obs.get("research", {})),
                ("In Progress", temp_obs.get("inprogress", {})),
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


class StarCraftMultiEnv(BaseEnv):
    @dataclass
    class Config:
        task: str

        map_idx: int
        player1_race: str
        player2_race: str
        
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
        
        self.player1_race = self.cfg.player1_race
        self.player2_race = self.cfg.player2_race
        
        self.action_description1 = ActionDescriptions(self.player1_race)
        self.action_dict_tmp = self.action_description1.action_descriptions
        self.action_dict1 = {}
        for category in self.action_dict_tmp:
            for key, value in self.action_dict_tmp[category].items():
                self.action_dict1[value.upper()] = key
        print("action_dict1", self.action_dict1)
        
        self.action_description2 = ActionDescriptions(self.player2_race)
        self.action_dict_tmp = self.action_description2.action_descriptions
        self.action_dict2 = {}
        for category in self.action_dict_tmp:
            for key, value in self.action_dict_tmp[category].items():
                self.action_dict2[value.upper()] = key
        print("action_dict2", self.action_dict2)

        self.query_interval = self.cfg.query_interval
        self.num_summaries = self.cfg.num_summaries
        self.num_actions = self.cfg.num_actions
        self.curr_action_step = 0

        self.summary1 = {}
        self.summary2 = {}
        self.executed_actions1 = []
        self.executed_actions2 = []

        self.lock1 = multiprocessing.Manager().Lock()
        self.lock2 = multiprocessing.Manager().Lock()
        
        self.transaction1 = multiprocessing.Manager().dict()
        self.transaction1.update(
            {'information': {}, 'reward': 0, 'action': None,
             'done': False, 'result': None, 'iter': 0, 'command': None, "output_command_flag": False,
             'action_executed': [], 'action_failures': [], })
        self.transaction2 = multiprocessing.Manager().dict()
        self.transaction2.update(
            {'information': {}, 'reward': 0, 'action': None,
             'done': False, 'result': None, 'iter': 0, 'command': None, "output_command_flag": False,
             'action_executed': [], 'action_failures': [], })
        
        self.isReadyForNextStep1 = multiprocessing.Event()
        self.isReadyForNextStep2 = multiprocessing.Event()
        
        self.game_end_event1 = multiprocessing.Event()
        self.game_end_event2 = multiprocessing.Event()
        
        self.game_over1 = multiprocessing.Value('b', False)
        self.game_over2 = multiprocessing.Value('b', False)
        
        self.done_event1 = multiprocessing.Event()
        self.done_event2 = multiprocessing.Event()
        
        self.p1 = None
        self.p2 = None

    def check_process(self, agent_num, reset=False):
        p = self.p1 if agent_num == 1 else self.p2
        game_end_event = self.game_end_event1 if agent_num == 1 else self.game_end_event2

        if p is not None:
            if p.is_alive():
                if not game_end_event.is_set():  # Check if the game is over
                    return  # If the game is not over, just return and do not restart the process
                p.terminate()
            p.join()

        if reset:
            self.transaction1.update(
                {'information': {}, 'reward': 0, 'action': None,
                 'done': False, 'result': None, 'iter': 0, 'command': None, "output_command_flag": False,
                 'action_executed': [], 'action_failures': [], })
            self.transaction2.update(
                {'information': {}, 'reward': 0, 'action': None,
                 'done': False, 'result': None, 'iter': 0, 'command': None, "output_command_flag": False,
                 'action_executed': [], 'action_failures': [], })
            
            self.game_end_event1.clear()  # Clear the game_end_event
            self.game_end_event2.clear()  # Clear the game_end_event

            p = multiprocessing.Process(target=sc2_run_multi_game, args=(
                self.transaction1, self.transaction2, self.lock1, self.lock2,
                self.isReadyForNextStep1, self.isReadyForNextStep2,
                self.game_end_event1, self.game_end_event2,
                self.done_event1, self.done_event2,
                self.map_name, self.log_path
            ))
            p.start()

            self.p1 = p
            self.p2 = p

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        self.check_process(1, reset=True)
        self.check_process(2, reset=True)

        self.game_end_event1.clear()
        self.game_end_event2.clear()
        
        state1 = from_dict(StarCraftObs, {'observation': self.transaction1['information']})
        state2 = from_dict(StarCraftObs, {'observation': self.transaction2['information']})
        
        return state1, state2

    def initial_obs(self) -> Obs:
        return self.reset()

    def obs2text(self, obs: Obs) -> str:
        if not obs.observation:
            return None
        else:
            return obs.to_text()

    def text2action(self, text: str, agent_id) -> Action:

        if agent_id == 1:
            action_dict = self.action_dict1
        elif agent_id == 2:
            action_dict = self.action_dict2

        individual_actions_pattern = r"\d+: <?([^>\n]+)>?"
        actions = re.findall(individual_actions_pattern, text)

        valid_actions = []

        for action in actions:
            action = action.upper()
            if action in action_dict:
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
    
    def action_step(self, action1, action2) -> tuple[Obs, float, bool, bool, dict[str, Any]]:

        with self.lock1:
            self.transaction1['action'] = action1
        with self.lock2:
            self.transaction2['action'] = action2
        
        while not (self.done_event1.is_set() or self.isReadyForNextStep1.is_set()):
            time.sleep(0.0001)
        
        if self.done_event1.is_set():
            self.done_event1.clear()
            self.isReadyForNextStep1.clear()
            self.game_over1.value = True
            if self.transaction1['result'].name == 'Victory':
                self.transaction1['reward'] += 50
        elif self.isReadyForNextStep1.is_set():
            self.isReadyForNextStep1.clear()
            self.check_process(1)
        
        while not (self.done_event2.is_set() or self.isReadyForNextStep2.is_set()):
            time.sleep(0.0001)
        
        if self.done_event2.is_set():
            self.done_event2.clear()
            self.isReadyForNextStep2.clear()
            self.game_over2.value = True
            if self.transaction2['result'].name == 'Victory':
                self.transaction2['reward'] += 50
        elif self.isReadyForNextStep2.is_set():
            self.isReadyForNextStep2.clear()
            self.check_process(2)
        
        state1 = self.transaction1['information']
        state2 = self.transaction2['information']

        return state1, state2, self.transaction1['done'], self.transaction2['done']

    def step(self, action1: Action, action2: Action) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        
        if self.curr_action_step == self.query_interval:
            self.summary1, self.summary2 = {}, {}
            self.executed_actions1, self.executed_actions2 = [], []
            self.curr_action_step = 0

        curr_action1 = self.action_dict1[action1.actions[0]]
        curr_action2 = self.action_dict2[action2.actions[0]]
        obs1, obs2, done1, done2 = self.action_step(curr_action1, curr_action2)
        
        done = done1 | done2
        self.executed_actions1.append(self.transaction1['action_executed'])
        self.executed_actions2.append(self.transaction2['action_executed'])

        if self.curr_action_step >= self.query_interval - self.num_summaries:
            summary_idx = self.curr_action_step - self.query_interval + self.num_summaries + 1
            self.summary1[f'Summary {summary_idx}'] = obs1
            self.summary2[f'Summary {summary_idx}'] = obs2

        state1 = from_dict(StarCraftObs, {'observation': self.summary1})
        state2 = from_dict(StarCraftObs, {'observation': self.summary2})

        self.curr_action_step += 1

        return state1, state2, 0, done, False, None

    def evaluate(self, obs1: Obs, obs2: Obs):
        result1 = self.transaction1['result']
        if result1 is None:
            result = None
        elif result1.name == 'Victory':
            result = 'Agent1 Win'
        else:
            result = 'Agent2 Win'
        
        done = self.transaction1['done'] | self.transaction2['done']

        return result, done

    def get_game_info(self, agent_id) -> dict:
        if agent_id == 1:
            return {
                "player_race": self.player1_race,
                "enemy_race": self.player2_race,
                "action_executed": self.executed_actions1,
                "action_dict": self.action_dict1,
                "num_actions": self.num_actions,
            }
        elif agent_id == 2:
            return {
                "player_race": self.player2_race,
                "enemy_race": self.player1_race,
                "action_executed": self.executed_actions2,
                "action_dict": self.action_dict2,
                "num_actions": self.num_actions,
            }