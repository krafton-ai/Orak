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
from diambra.arena import EnvironmentSettings, SpaceTypes
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
    "Ken": {
        "Fireball (Hadouken)": {"right": [7, 6, 5, 10], "left": [7, 8, 1, 10]},
        "Dragon Punch (Shoryuken)": {
            "right": [MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["High Punch"]],
            "left": [MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["High Punch"]],
        },
        "Hurricane Kick (Tatsumaki Senpukyaku)": {
            "right": [MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["Low Kick"]],
            "left": [MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["Low Kick"]],
        },
    },
    "Q": {
        "High Speed Barrage": {
            "right": [MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["High Punch"]],
            "left": [MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["High Punch"]],
        },
        "Capture and Deadly Blow": {
            "right": [MOVES["Right"], MOVES["Down+Right"], MOVES["Down"], MOVES["Down+Left"], MOVES["Low Kick"]],
            "left": [MOVES["Left"], MOVES["Down+Left"], MOVES["Down"], MOVES["Down+Right"], MOVES["Low Kick"]],
        },
    },
    "Chun-Li": {
        "Kikkoken": {
            "right": [MOVES["Left"], MOVES["Down+Left"], MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["Medium Punch"]],
            "left": [MOVES["Right"], MOVES["Down+Right"], MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["Medium Punch"]],
        },
        "Hyakuretsukyaku": {
            "right": [MOVES["Medium Kick"], MOVES["Medium Kick"], MOVES["Medium Kick"]],
            "left": [MOVES["Medium Kick"], MOVES["Medium Kick"], MOVES["Medium Kick"]],
        },
        "Flip Kick": {
            "right": [MOVES["Right"], MOVES["Down+Right"], MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["Medium Kick"]],
            "left": [MOVES["Left"], MOVES["Down+Left"], MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["Medium Kick"]],
        },
    },
}

SPECIAL_MOVES = {
    "Ken": {
        "EX-Fireball (Hadouken)": {
            "right": [7, 6, 5, 10, 10],
            "left": [7, 8, 1, 10, 10],
        },
        "EX-Dragon Punch (Shoryuken)": {
            "right": [MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["High Punch"], MOVES["High Punch"]],
            "left": [MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["High Punch"], MOVES["High Punch"]],
        },
        "Super Dragon Punch (Shouryuu-Reppa)": {
            "right": [MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["High Punch"]],
            "left": [MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["High Punch"]],
        },
        "Shippuu-Jinrai-Kyaku": {
            "right": [MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["Low Kick"]],
            "left": [MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["Low Kick"]],
        },
    },
    "Q": {
        "Total Destruction": {
            "right": [MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["High Punch"]],
            "left": [MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["High Punch"]],
        }
    },
    "Chun-Li": {
        "Tensei Ranka": {
            "right": [MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["Down"], MOVES["Down+Right"], MOVES["Low Kick"]],
            "left": [MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["Down"], MOVES["Low Kick"]],
        },
    },
}

META_INSTRUCTIONS = {
    "Ken": {
        "Move Closer": {"right": [5, 5, 5, 5], "left": [1, 1, 1, 1]},
        "Move Away": {"right": [1, 1, 1, 1], "left": [5, 5, 5, 5]},
        "Fireball": COMBOS["Ken"]["Fireball (Hadouken)"],
        "Megapunch": COMBOS["Ken"]["Dragon Punch (Shoryuken)"],
        "Hurricane": COMBOS["Ken"]["Hurricane Kick (Tatsumaki Senpukyaku)"],
        "Megafireball": SPECIAL_MOVES["Ken"]["EX-Fireball (Hadouken)"],
        # "Super attack 2": SPECIAL_MOVES["Ken"]["EX-Dragon Punch (Shoryuken)"],
        # "Super attack 3": SPECIAL_MOVES["Ken"]["Super Dragon Punch (Shouryuu-Reppa)"],
        "Super attack 4": SPECIAL_MOVES["Ken"]["Shippuu-Jinrai-Kyaku"],
        **{
            move_name: {"right": [move_nb, 0], "left": [move_nb, 0]}
            for move_name, move_nb in MOVES.items()
            if "Punch" in move_name or "Kick" in move_name
        },
        "Jump Closer": {"right": [4, 4, 4, 4], "left": [2, 2, 2, 2]},
        "Jump Away": {"right": [2, 2, 2, 2], "left": [4, 4, 4, 4]},
    },
    "Q": {
        "Move Closer": {"right": [5, 5, 5, 5], "left": [1, 1, 1, 1]},
        "Move Away": {"right": [1, 1, 1, 1], "left": [5, 5, 5, 5]},
        "High Speed Barrage": COMBOS["Q"].get("High Speed Barrage", {}),
        "Capture and Deadly Blow": COMBOS["Q"].get("Capture and Deadly Blow", {}),
        "Super attack": SPECIAL_MOVES["Q"].get("Total Destruction", {}),
        **{
            move_name: {"right": [move_nb, 0], "left": [move_nb, 0]}
            for move_name, move_nb in MOVES.items()
            if "Punch" in move_name or "Kick" in move_name
        },
        "Jump Closer": {"right": [4, 4, 4, 4], "left": [2, 2, 2, 2]},
        "Jump Away": {"right": [2, 2, 2, 2], "left": [4, 4, 4, 4]},
    },
    "Chun-Li": {
        "Move Closer": {"right": [5, 5, 5, 5], "left": [1, 1, 1, 1]},
        "Move Away": {"right": [1, 1, 1, 1], "left": [5, 5, 5, 5]},
        "Kikkoken": COMBOS["Chun-Li"]["Kikkoken"],
        "Hyakuretsukyaku": COMBOS["Chun-Li"]["Hyakuretsukyaku"],
        "Flip Kick": COMBOS["Chun-Li"]["Flip Kick"],
        "Super attack": SPECIAL_MOVES["Chun-Li"]["Tensei Ranka"],
        **{
            move_name: {"right": [move_nb, 0], "left": [move_nb, 0]}
            for move_name, move_nb in MOVES.items()
            if "Punch" in move_name or "Kick" in move_name
        },
        "Jump Closer": {"right": [4, 4, 4, 4], "left": [2, 2, 2, 2]},
        "Jump Away": {"right": [2, 2, 2, 2], "left": [4, 4, 4, 4]},
    },
}

META_INSTRUCTIONS_WITH_LOWER = {
    "Ken": {
        **META_INSTRUCTIONS["Ken"],
        **{key.lower(): value for key, value in META_INSTRUCTIONS["Ken"].items()},
        "lower": {"right": [12, 0], "left": [12, 0]},
        "medium": {"right": [13, 0], "left": [13, 0]},
        "med": {"right": [13, 0], "left": [13, 0]},
        "high": {"right": [14, 0], "left": [14, 0]},
    },
    "Q": {
        **META_INSTRUCTIONS["Q"],
        **{key.lower(): value for key, value in META_INSTRUCTIONS["Q"].items()},
        "lower": {"right": [12, 0], "left": [12, 0]},
        "medium": {"right": [13, 0], "left": [13, 0]},
        "med": {"right": [13, 0], "left": [13, 0]},
        "high": {"right": [14, 0], "left": [14, 0]},
    },
    "Chun-Li": {
        **META_INSTRUCTIONS["Chun-Li"],
        **{key.lower(): value for key, value in META_INSTRUCTIONS["Chun-Li"].items()},
        "lower": {"right": [12, 0], "left": [12, 0]},
        "medium": {"right": [13, 0], "left": [13, 0]},
        "med": {"right": [13, 0], "left": [13, 0]},
        "high": {"right": [14, 0], "left": [14, 0]},
    },
}

MOVE_LIST = "- " + "\n - ".join([
    move for char_dict in META_INSTRUCTIONS.values() for move in char_dict.keys()
    if move is not None and move != ""
])
KEN_RED = [248, 0, 0]
Q_BROWN = [169, 140, 116] 
CHUN_LI_BLUE = [0, 102, 204] 

CHARACTER_COLORS = {
    "Ken": KEN_RED,
    "Q": Q_BROWN,
    "Chun-Li": CHUN_LI_BLUE,
}

@dataclass
class StreetFighterObs(Obs):
    observation: dict
    reward: int
    log_path: str
    terminated: bool
    truncated: bool
    info: dict
    current_direction: str
    character: str
    image: Image.Image = None

    def to_text(self):
        # Position Prompt
        l2_distance = 0

        position_prompt = ""
        position_prompt += f"Your opponent is on the {self.current_direction}. "
        image = Image.fromarray(np.array(self.observation["frame"]))
        # current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # image.save(f"screenshots/sf3_{current_time}.png")
        # print("image saved")
        model = YOLO("yolo11n.pt")
        results = model(image)

        # annotated_frame = results[0].plot()
        # cv2.imwrite(f"screenshots/sf3_annotated_{current_time}.png", annotated_frame)

        # Get Normalized xywhn
        xywhn = results[0].boxes.xywhn 
        names = [results[0].names[cls.item()] for cls in results[0].boxes.cls.int()] 

        
        # 1st filter
        target_classes = {'person', 'teddy bear'} # filtered class
        mask = np.array([name in target_classes for name in names])
        filtered_xywhn = xywhn[mask]
        # print(xywhn, filtered_xywhn, names)

        # 2nd filter (box size)
        mask_2 = (filtered_xywhn[:,2] * filtered_xywhn[:,3]) >= 0.05
        filtered_xywhn_2 = filtered_xywhn[mask_2]
        # print(filtered_xywhn_2)


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

        
        player_name = IDX_TO_CHARACTER.get(self.observation['P1']['character'], "Unknown")
        opponent_name = IDX_TO_CHARACTER.get(self.observation['P2']['character'], "Unknown")

        obs_text = (f"You are playing {player_name} in Street Fighter 3. Your opponent is {opponent_name}. \n"
        f"Your Current Direction: {self.current_direction} \n"
        f"Distance from Opponent: {position} \n"
        f"Time Remaining: {self.observation['timer'][0]} \n"
        f"Health: \n"
        f"    Your Health: {self.observation['P1']['health'][0]+1} \n"
        f"    Opponent's Health: {self.observation['P2']['health'][0]+1} \n"
        f"Super Bar Guage: \n"
        f"    Your Super Bar Guage: {self.observation['P1']['super_bar'][0]} \n"
        f"    Opponent's Super Bar Guage: {self.observation['P2']['super_bar'][0]}  \n"
        f"Super Count (Count of activated super move): \n"
        f"    Your Super Count: {self.observation['P1']['super_count'][0]} \n"
        f"    Opponent's Super Count: {self.observation['P2']['super_count'][0]}  \n"
        f"Stun Bar Guage: \n"
        f"    Your Stun Bar Guage:  {self.observation['P1']['stun_bar'][0]} \n"
        f"    Opponent's Stun Bar Guage: {self.observation['P2']['stun_bar'][0]} \n"
        f"IsStunned (0: not stunned, 1: stunned): \n"
        f"    Your Status: {self.observation['P1']['stunned']}\n"
        f"    Opponent's Special Status: {self.observation['P2']['stunned']}"
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


class StreetFighterEnv(BaseEnv):
    @dataclass
    class Config:
        difficulty: int  # 1 to 8
        # max_steps: int
        character: str
        log_path: str
        task: str
        input_modality: str = "text"

    cfg: Config

    def configure(self):
        self.difficulty = self.cfg.difficulty
        self.character = self.cfg.character
        self.observations = []
        self.current_direction = None
        self.previous_actions = []
        if self.character == "Q":
            self.character_color = Q_BROWN
        elif self.character == "Ken":
            self.character_color = KEN_RED
        else:
            self.character_color = CHARACTER_COLORS.get(self.character, KEN_RED)
        self.log_path = self.cfg.log_path
        self.input_modality = self.cfg.input_modality

        self.use_image = self.input_modality in ["image", "text_image"]
        self.step_count = 0

        # Game Environment settings
        settings = EnvironmentSettings()
        settings.action_space = SpaceTypes.DISCRETE

        settings.difficulty = self.difficulty
        settings.characters = self.character

        # self._env = diambra.arena.make()
        self._env = diambra.arena.make("sfiii3n", settings, render_mode="human")
        # save settings to a text file
        with open(f"settings.txt", "w") as f:
            f.write(str(settings))
        _, _ = self._env.reset(seed=42)
        self._env.render()

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

    def get_pil_image(self):
        # Return None if there are no observations
        if not self.observations:
            return None
        # Get the most recent observation
        obs = self.observations[-1]
        # Convert the frame to a PIL Image
        image = Image.fromarray(np.array(obs["frame"]))
        return image

    def initial_obs(self) -> Obs:
        image = None
        if self.use_image:
            image = self.get_pil_image()  # TODO: add image

        # self._env.render()
        observation, reward, terminated, truncated, info = self._env.step(
            0
        )

        self.current_direction = self.observe(observation)

        obs = StreetFighterObs(
            observation=observation,
            reward=reward,
            log_path=self.log_path,
            terminated=terminated,
            truncated=truncated,
            info=info,
            current_direction=self.current_direction,
            character=self.character,
            image=image,
        )
        return obs

    def obs2text(self, obs: Obs) -> str:
        if not self.use_image:
            text = obs.to_text()
            return text
        else:
            return ""
        
    def text2action(self, text: str) -> Action:
        matches = re.findall(r"-?\s*\**([\w ]+)\**", text)

        moves = ["".join(match) for match in matches]
        invalid_moves = []
        valid_moves = []
        for move in moves:
            cleaned_move_name = move.strip().lower()
            if cleaned_move_name in META_INSTRUCTIONS_WITH_LOWER[self.character].keys():
                valid_moves.append(cleaned_move_name)
            else:
                invalid_moves.append(move)
        if len(invalid_moves) > 1:
            print(f"Many invalid moves: {invalid_moves}")

        next_buttons_to_press = [
            button
            for combo in valid_moves
            for button in META_INSTRUCTIONS_WITH_LOWER[self.character][combo][
                self.current_direction  # Direction.
            ]
            # We add a wait time after each button press
            + [0] * NB_FRAME_WAIT
        ]
        if len(next_buttons_to_press) == 0:
            return StreetFighterAction(actions=[0])

        return StreetFighterAction(actions=next_buttons_to_press)

    def step(self, action: Action) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        for _action in action:
            self._env.render()
            observation, reward, terminated, truncated, info = self._env.step(
                _action
            )
        self.current_direction = self.observe(observation)

        image = None
        if self.use_image:
            image = self.get_pil_image()
            self.step_count += 1
            image_path = f"{self.log_path}/step_{self.step_count:04d}.png"
            image.save(image_path)
        
        obs = StreetFighterObs(
            observation=observation,
            reward=reward,
            log_path=self.log_path,
            terminated=terminated,
            truncated=truncated,
            info=info,
            current_direction=self.current_direction,
            character=self.character,
            image=image,
        )

        return obs, 0, obs.terminated, obs.truncated, {}

    def evaluate(self, obs: Obs):
        done = obs.terminated | obs.truncated
        return int(obs.observation['stage'].item()), done

    def get_game_info(self) -> dict:
        skill_library = get_move_list_for_character(self.character)
        return {
            "skill_library": skill_library,
            "prev_state_str": None,
            "task_description": "Defeat the opponent"
        }

def get_move_list_for_character(character):
    # Return only the skill names for the given character
    return "- " + "\n - ".join([
        move for move in META_INSTRUCTIONS.get(character, {}).keys()
        if move is not None and move != ""
    ])
