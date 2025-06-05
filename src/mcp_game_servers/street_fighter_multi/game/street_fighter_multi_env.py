import json
import re
import datetime
import os
import cv2

from dataclasses import dataclass, field
from typing import Any, Iterator, List
from PIL import Image
from ultralytics import YOLO

import diambra.arena
import numpy as np
from diambra.arena import EnvironmentSettingsMultiAgent, SpaceTypes
from rich import print

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.utils.types.game_io import Action, Obs

NB_FRAME_WAIT = 0

MOVES = {
    "No-Move": 0,
    "Left": 1,
    "Left+Up": 2,
    "Up+Left": 2,
    "Up": 3,
    "Up+Right": 4,
    "Right+Up": 4,
    "Right": 5,
    "Right+Down": 6,
    "Down+Right": 6,
    "Down": 7,
    "Down+Left": 8,
    "Left+Down": 8,
    "Low Punch": 9,
    "Medium Punch": 10,
    "High Punch": 11,
    "Low Kick": 12,
    "Low": 12,
    "Medium Kick": 13,
    "Medium": 13,
    "High Kick": 14,
    "Low Punch+Low Kick": 15,
    "Medium Punch+Medium Kick": 16,
    "High Punch+High Kick": 17,
}

IDX_TO_CHARACTER = {
    0: "Alex", 
    1: "Twelve", 
    2: "Hugo", 
    3: "Sean", 
    4: "Makoto", 
    5: "Elena", 
    6: "Ibuki", 
    7: "Chun-Li", 
    8: "Dudley", 
    9: "Necro", 
    10: "Q", 
    11: "Oro", 
    12: "Urien", 
    13: "Remy", 
    14: "Ryu", 
    15: "Gouki", 
    16: "Yun", 
    17: "Yang", 
    18: "Ken", 
    19: "Gill",
}

MOVES_WITH_LOWER = {
    **MOVES,
    **{key.lower(): value for key, value in MOVES.items()},
}

COMBOS = {
    "Fireball (Hadouken)": {"right": [7, 6, 5, 10], "left": [7, 8, 1, 10]},
    # Refacto with command names
    "Dragon Punch (Shoryuken)": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Punch"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["High Punch"],
        ],
    },
    "Hurricane Kick (Tatsumaki Senpukyaku)": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Low Kick"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Low Kick"],
        ],
    },
}

SPECIAL_MOVES = {
    "EX-Fireball (Hadouken)": {
        "right": [7, 6, 5, 10, 10],
        "left": [7, 8, 1, 10, 10],
    },
    "EX-Dragon Punch (Shoryuken)": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Punch"],
            MOVES["High Punch"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["High Punch"],
            MOVES["High Punch"],
        ],
    },
    "Super Dragon Punch (Shouryuu-Reppa)": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Punch"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["High Punch"],
        ],
    },
    "Shippuu-Jinrai-Kyaku": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Punch"],
            MOVES["Low Kick"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Low Kick"],
        ],
    },
}

META_INSTRUCTIONS = {
    "Move Closer": {"right": [5, 5, 5, 5], "left": [1, 1, 1, 1]},
    "Move Away": {"right": [1, 1, 1, 1], "left": [5, 5, 5, 5]},
    "Fireball": COMBOS["Fireball (Hadouken)"],
    "Megapunch": COMBOS["Dragon Punch (Shoryuken)"],
    "Hurricane": COMBOS["Hurricane Kick (Tatsumaki Senpukyaku)"],
    "Megafireball": SPECIAL_MOVES["EX-Fireball (Hadouken)"],
    "Super attack 2": SPECIAL_MOVES["EX-Dragon Punch (Shoryuken)"],
    "Super attack 3": SPECIAL_MOVES["Super Dragon Punch (Shouryuu-Reppa)"],
    "Super attack 4": SPECIAL_MOVES["Shippuu-Jinrai-Kyaku"],
    **{
        move_name: {"right": [move_nb, 0], "left": [move_nb, 0]}
        for move_name, move_nb in MOVES.items()
        if "Punch" in move_name or "Kick" in move_name
    },
    "Jump Closer": {"right": [4, 4, 4, 4], "left": [2, 2, 2, 2]},
    "Jump Away": {"right": [2, 2, 2, 2], "left": [4, 4, 4, 4]},
}
META_INSTRUCTIONS_WITH_LOWER = {
    **META_INSTRUCTIONS,
    **{key.lower(): value for key, value in META_INSTRUCTIONS.items()},
    ## Also add the combos for Lower, Medium and High
    "lower": {"right": [12, 0], "left": [12, 0]},
    "medium": {"right": [13, 0], "left": [13, 0]},
    "med": {"right": [13, 0], "left": [13, 0]},
    "high": {"right": [14, 0], "left": [14, 0]},
}


MOVE_LIST = "- " + "\n - ".join([move for move in META_INSTRUCTIONS])
KEN_RED = [248, 0, 0]



@dataclass
class StreetFighterMultiObs(Obs):
    observation: dict
    reward: int
    terminated: bool
    truncated: bool
    info: dict
    current_direction: str
    task: str
    character_1p: str
    character_2p: str
    log_path: str
    image: Image.Image = None
    player_id: int = 1

    def to_text(self):
        current_direction_2p = "right" if self.current_direction == "left" else "left"
        # Position Prompt
        l2_distance = 0

        position_prompt = ""
        position_prompt += f"Player 1's opponent is on the {self.current_direction}. "
        position_prompt += f"Player 2's opponent is on the {current_direction_2p}. "

        image = Image.fromarray(np.array(self.observation["frame"]))

        model = YOLO("yolo11n.pt")
        results = model(image)

        # Get Normalized xywhn
        xywhn = results[0].boxes.xywhn 
        names = [results[0].names[cls.item()] for cls in results[0].boxes.cls.int()] 

        
        # 1st filter
        target_classes = {'person', 'teddy bear'} # filtered class
        mask = np.array([name in target_classes for name in names])
        filtered_xywhn = xywhn[mask]

        # 2nd filter (box size)
        mask_2 = (filtered_xywhn[:,2] * filtered_xywhn[:,3]) >= 0.05
        filtered_xywhn_2 = filtered_xywhn[mask_2]


        if filtered_xywhn_2.shape[0] == 2:
            l2_distance = np.linalg.norm(filtered_xywhn_2[0, :2] - filtered_xywhn_2[1,:2])
            print("Two characters detected. Length:", l2_distance) # Normalized length between characters

        position = "very close"

        if l2_distance > 0.4:
            position = "far"
        elif l2_distance >= 0.2:
            position = "close"
        else:
            position = "very close"

        
        player1_name = IDX_TO_CHARACTER.get(self.observation['P1']['character'], "Unknown")
        player2_name = IDX_TO_CHARACTER.get(self.observation['P2']['character'], "Unknown")

        obs_text = (f"You are Player {self.player_id}. Your goal is to defeat your opponent (Player {3 - self.player_id}). \n"
        f"Player 1 plays {player1_name}. Player2 plays {player2_name}. \n"
        f"Player 1 is facing {self.current_direction}. \n"
        f"Player 2 is facing {current_direction_2p}. \n"
        f"Distance from Opponent: {position} \n"
        f"Time Remaining: {self.observation['timer'][0]} \n"
        f"Health: \n"
        f"    Player 1's Health: {self.observation['P1']['health'][0]+1} \n"
        f"    Player 2's Health: {self.observation['P2']['health'][0]+1} \n"
        f"Power Bar Guage: \n"
        f"    Player 1's Power Bar Guage: {self.observation['P1']['super_bar'][0]} \n"
        f"    Player 2's Power Bar Guage: {self.observation['P2']['super_bar'][0]}  \n"
        f"Stun Bar Guage:  \n"
        f"    Player 1's Stun Bar Guage:  {self.observation['P1']['stun_bar'][0]} \n"
        f"    Player 2's Stun Bar Guage: {self.observation['P2']['stun_bar'][0]} \n"
        f"IsStunned (0: not stunned, 1: stunned): \n"
        f"    Player 1's Spetial Status: {self.observation['P1']['stunned']}\n"
        f"    Player 2's Special Status: {self.observation['P2']['stunned']}"
        )
        return obs_text


@dataclass
class StreetFighterAction(Action):
    actions: List[int] = field(default_factory=list)

    def __iter__(self) -> Iterator[int]:
        return iter(self.actions)

    def __getitem__(self, index: int) -> int:
        return self.actions[index]

    def __len__(self) -> int:
        return len(self.actions)

    def to_json(self) -> str:
        return json.dumps(self.actions)


def detect_position_from_color(
    observation: dict, color: list, epsilon=1, save_frame: bool = False
) -> tuple:
    """
    Convert the observation from pixels to player coordinates.

    It works by finding the first pixel that matches the color.

    Returns a tuple of (x, y) coordinates.
    - x is between 0 and 384
    - y is between 0 and 224
    """
    frame = observation["frame"]
    # the screen is a np.array of RGB colors (3 channels)
    # Select the frames where the characters play: between 80 vertical and 200 vertical
    # print(frame.shape)
    # dump the observation to a file for debugging
    # if save_frame:
    #     np.save("observation.npy", frame)

    frame = frame[100:200, :]

    # Detect the red color of Ken
    diff = np.linalg.norm(np.array(frame) - np.array(color), axis=2)
    mask = diff < epsilon

    # Return the index where the red color is detected
    coordinates = mask.nonzero()

    if len(coordinates[0]) == 0:
        return None

    # Add back the vertical offset
    first_match = (coordinates[1][0], coordinates[0][0] + 100)
    return first_match


class StreetFighterMultiEnv(BaseEnv):
    @dataclass
    class Config:
        max_steps: int
        character_1p: str
        character_2p: str
        log_path: str
        task: str
        input_modality: str

    cfg: Config

    def configure(self):
        self.character_1p = self.cfg.character_1p
        self.character_2p = self.cfg.character_2p
        self.observations = []
        self.current_direction = None
        self.previous_actions = []
        self.character_color = KEN_RED
        self.log_path = self.cfg.log_path

        # Game Environment settings
        settings = EnvironmentSettingsMultiAgent()
        settings.action_space = (SpaceTypes.DISCRETE, SpaceTypes.DISCRETE)
        settings.characters = [self.character_1p, self.character_2p]
        settings.super_art = [3, 3] # Ken super arts

#        settings.characters = self.character

        self._env = diambra.arena.make("sfiii3n", settings, render_mode="human")

        return 0

    def observe(self, observation: dict):
        """
        The robot will observe the environment by calling this method.

        The latest observations are at the end of the list.
        """

        # detect the position of characters
        observation["character_position"] = detect_position_from_color(
            observation, self.character_color
        )

        self.observations.append(observation)

        # Delete the oldest observation if we have more than 10 observations
        if len(self.observations) > 10:
            self.observations.pop(0)

        character_position = observation.get("character_position")
        if character_position is not None:
            if character_position[0] < 190:
                return "right"
            return "left"

        # Keep track of the current direction by checking the position of the character
        if observation["P1"]["side"] == 0:
            return "right"
        return "left"

    def initial_obs(self) -> Obs:
        observation, info = self._env.reset(seed=42)
        initial_action = {'agent_0': 0, 'agent_1': 0}
        self._env.render()
        observation, reward, terminated, truncated, info = self._env.step(
            initial_action
        )

        self.current_direction = self.observe(observation)

        obs1 = StreetFighterMultiObs(
            observation=observation,
            reward=reward,
            terminated=terminated,
            truncated=truncated,
            info=info,
            task=self.cfg.task,
            current_direction=self.current_direction,
            character_1p=self.character_1p,
            character_2p=self.character_2p,
            log_path=self.cfg.log_path,
            player_id=1
        )


        obs2 = StreetFighterMultiObs(
            observation=observation,
            reward=reward,
            terminated=terminated,
            truncated=truncated,
            info=info,
            task=self.cfg.task,
            current_direction=self.current_direction,
            character_1p=self.character_1p,
            character_2p=self.character_2p,
            log_path=self.cfg.log_path,
            player_id=2
        )

        return obs1, obs2

    def obs2text(self, obs: Obs) -> str:
        text = obs.to_text()
        return text

    def text2action(self, text: str, agent_id = None) -> Action:
        matches = re.findall(r"-?\s*\**([\w ]+)\**", text)
        moves = ["".join(match) for match in matches]
        invalid_moves = []
        valid_moves = []
        for move in moves:
            cleaned_move_name = move.strip().lower()
            if cleaned_move_name in META_INSTRUCTIONS_WITH_LOWER.keys():
                valid_moves.append(cleaned_move_name)
            else:
                invalid_moves.append(move)
        if len(invalid_moves) > 1:
            print(f"Many invalid moves: {invalid_moves}")

        if agent_id == 2:
            agent_2_direction = "right" if self.current_direction == "left" else "left"

            next_buttons_to_press = [
                button
                for combo in valid_moves
                for button in META_INSTRUCTIONS_WITH_LOWER[combo][
                    agent_2_direction  # MODIFY THIS
                ]
                # We add a wait time after each button press
                + [0] * NB_FRAME_WAIT
            ]
        else:
            next_buttons_to_press = [
                button
                for combo in valid_moves
                for button in META_INSTRUCTIONS_WITH_LOWER[combo][
                    self.current_direction  # Direction.
                ]
                # We add a wait time after each button press
                + [0] * NB_FRAME_WAIT
            ]
        
        if len(next_buttons_to_press) == 0:
            return StreetFighterAction(actions=[0, 0, 0, 0])

        return StreetFighterAction(actions=next_buttons_to_press)

    def step(self, action1, action2) -> tuple[Obs, Obs, float, bool, bool, dict[str, Any]]:
        for _action1, _action2 in zip(action1, action2):
            self._env.render()
            observation, reward, terminated, truncated, info = self._env.step(
                {'agent_0': _action1, 'agent_1': _action2}
            )
        self.current_direction = self.observe(observation)

        obs1 = StreetFighterMultiObs(
            observation=observation,
            reward=reward,
            terminated=terminated,
            truncated=truncated,
            info=info,
            task=self.cfg.task,
            current_direction=self.current_direction,
            character_1p=self.character_1p,
            character_2p=self.character_2p,
            log_path=self.cfg.log_path,
            player_id=1
        )

        obs2 = StreetFighterMultiObs(
            observation=observation,
            reward=reward,
            terminated=terminated,
            truncated=truncated,
            info=info,
            task=self.cfg.task,
            current_direction=self.current_direction,
            character_1p=self.character_1p,
            character_2p=self.character_2p,
            log_path=self.cfg.log_path,
            player_id=2
        )

        return obs1, obs2, reward, terminated, truncated, info

    def evaluate(self, obs: Obs, obs2: Obs):
        done = obs.terminated | obs.truncated
        p1_wins = obs.observation["P1"]["wins"][0]
        p2_wins = obs.observation["P2"]["wins"][0]
        ment = None
        if p1_wins == 2 or p2_wins == 2:
            player_1_won = p1_wins == 2
            if player_1_won:
                ment = f"P1:P2 = {p1_wins}:{p2_wins}. Player1 won!"
            else:
                ment = f"P1:P2 = {p1_wins}:{p2_wins}. Player2 won!"
        return ment, done
#        return int(obs.observation['stage'].item()), done

    def get_game_info(self, agent_id = None) -> dict:
        skill_library = f"""{MOVE_LIST}"""

        return {
            "skill_library": skill_library,
            "prev_state_str": None,
            "task_description": "Defeat the opponent"
        }
