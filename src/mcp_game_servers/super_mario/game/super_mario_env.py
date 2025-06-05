import sys
import os.path
import json
import time
import requests

from dataclasses import dataclass, field
from typing import SupportsFloat, Any, Tuple, Dict, Iterator, List

import gym
from gymnasium.core import ObsType
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace
from gym.wrappers import FrameStack, GrayScaleObservation, TransformObservation
from mcp_game_servers.super_mario.game.wrappers import ResizeObservation, SkipFrame

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.utils.types.game_io import Action, Obs # gamingslm/src/mcp_game_servers/super_mario/game

import torch
import numpy as np
import random
import cv2
from PIL import Image
import datetime

import io
import base64
from gym.wrappers.frame_stack import LazyFrames

from pathlib import Path
#from mcp_game_servers.super_mario.game.mario_rl_agent import Mario

from gym.utils.play import play


@dataclass
class SuperMarioObs(Obs):
    time: str = field(default=datetime.datetime.now().strftime('%Y%m%d_%H%M%S'), init=False)
    state: dict
    info: dict #{'coins': 0, 'flag_get': False, 'life': 2, 'score': 0, 'stage': 1, 'status': 'small', 'time': 394, 'world': 1, 'x_pos': 240, 'y_pos': 141}
    reward: dict
    object_pattern_file: str = field(default='src/mcp_game_servers/super_mario/game/all_object_patterns.json', init=False)
    thresholds: dict = field(default_factory=lambda: {
        "0_brick_brown" : 0.8,
        "1_question_block_light" : 0.8,
        "1_question_block_mild" : 0.8,
        "1_question_block_dark" : 0.8,
        "2_inactivated_block" : 0.8,
        "3_monster_mushroom" : 0.6,
        "4_monster_turtle" : 0.6,
        "5_pit_1start" : 0.8, 
        "5_pit_2end" : 0.8,
        "6_pipe_green" : 0.8,
        "7_item_mushroom_red" : 0.8,
        "7_item_mushroom_green" : 0.7,
        "8_stair" : 0.75, # 0.7< x <
        "9_flag" : 0.8,
    }, init=False)
    image: Image.Image = None

    def __post_init__(self):
        with open(self.object_pattern_file, 'r') as json_file:
            self.object_patterns = json.load(json_file)

    def save_state_image(self, state):
        state = torch.FloatTensor(state)[0]
        state = state * 255.0
        array_255 = state.numpy().astype(np.uint8) # LeftTop to RightBottom; from (0,0,c) -> (-y, x, c)

        image = Image.fromarray(array_255)

        self.time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        image.save(f"screenshot/{self.time}.png")

    def find_objects_in_state(self, state, object_patterns):
        found_objects = {}  # Dictionary to store found objects

        # state to np.array
        state = torch.FloatTensor(state)[0]
        state = state * 255.0
        big_image = state.numpy().astype(np.uint8)
        if big_image.ndim == 3:
            big_image = cv2.cvtColor(big_image, cv2.COLOR_BGR2GRAY) # (240, 256)
        
        for object_name, small_object in object_patterns.items():
            if "question_block_" in object_name:
                object_key = "1_question_block"
            elif "item_mushroom" in object_name:
                object_key = "8_item_mushroom"
            else:
                object_key = object_name
            
            if "question_block_" in object_name and "1_question_block" in found_objects.keys():
                if len(found_objects["1_question_block"])!=0:
                    continue
            
            if object_key not in found_objects:
                found_objects[object_key] = []
            
            # object to np.array
            small_object = torch.FloatTensor(small_object)[0]
            small_object = small_object * 255.0
            small_object = np.array(small_object, dtype=np.uint8)
            if small_object.ndim == 3 and small_object.shape[0] in [1, 3]:
                small_object = np.transpose(small_object, (1, 2, 0))  # Convert to HWC if in CHW
            if small_object.ndim == 3:
                small_object = cv2.cvtColor(small_object, cv2.COLOR_BGR2GRAY)

            # Perform template matching
            result = cv2.matchTemplate(big_image, small_object, cv2.TM_CCOEFF_NORMED)

            # Check if the object is in the image
            threshold = self.thresholds[object_name]
            locations = np.where(result >= threshold)

            for loc in zip(*locations[::-1]):  # Switch to (x, y)
                loc = (loc[0], 240-loc[1]) # Bottom-to-Top
                #print(f"Object '{object_name}' found at location: {loc}")
                found_objects[object_key].append(loc)

        print("self.time: ", self.time)
        print("found_objects: ", found_objects)
        return found_objects

    def to_text(self):
        observation = ""

        #self.save_state_image(self.state['image'])
        found_objects = self.find_objects_in_state(self.state['image'], self.object_patterns)

        # Mario loc
        x_pos = min(128, self.info['x_pos'])-6 # 6: adjusting value 
        y_pos = self.info['y_pos']-34 # 34: adjusting value 
        observation += f"Position of Mario: ({x_pos}, {y_pos})\n"
        
        # Object loc
        object_transform = {
            "brick": lambda x, y: f'({x},{y+1})',
            "question_block": lambda x, y: f'({x-1},{y+1})',
            "inactivated_block": lambda x, y: f'({x-1},{y+1})',
            "monster_mushroom": lambda x, y: f'({x-4},{y+2})',
            "monster_turtle": lambda x, y: f'({x-4},{y+10})',
            "pit_1start": lambda x, y: f'({x+8},{y})',
            "pit_2end": lambda x, y: f'({x+4},{y})',
            "pipe": lambda x, y: f'({x-4},{y},{y-32})',
            "item_mushroom": lambda x, y: f'({x-1},{y+1})',
            "stair": lambda x, y: f'({x},{y})',
            "flag": lambda x, y: f'({x-2},{y})',
        }
        object_label = {
            "brick": "- Bricks: {}",
            "question_block": "- Question Blocks: {}",
            "inactivated_block": "- Inactivated Blocks: {}",
            "monster_mushroom": "- Monster Goomba: {}",
            "monster_turtle": "- Monster Koopas: {}",
            "pit_1start": "- Pit: start at {}",
            "pit_2end": ", end at {}",
            "pipe": "- Warp Pipe: {}",
            "item_mushroom": "- Item Mushrooms: {}",
            "stair": "- Stair Blocks: {}",
            "flag": "- Flag: {}",
        }

        observation += "Positions of all objects\n"
        for object, loc_list in found_objects.items():
            for key in object_transform:
                if key in object:
                    if not loc_list:
                        locs = "None"
                    else:
                        locs = ', '.join(object_transform[key](x, y) for x, y in loc_list)

                    label = object_label[key].format(locs)

                    if key == "pit_1start":
                        observation += label
                    elif key == "pit_2end":
                        observation += label + "\n"
                    else:
                        observation += label + "\n"
                    break

        observation += "(Note: All (x, y) positions refer to the top-left corner of each object.)\n"
        
        #print("observation: ", observation)
        return observation

    def evaluate(self):
        return int(self.reward['distance']), self.reward['done']

@dataclass
class SuperMarioAction(Action):
    values: Dict[str, str] = field(default_factory=dict)

class SuperMarioEnv(BaseEnv):
    @dataclass
    class Config:
        task: str
        logging: bool
        log_path: str
        input_modality: str = "text"

    cfg: Config

    def configure(self):
        self.task = self.cfg.task

        self.logging = self.cfg.logging
        self.log_path = self.cfg.log_path

        # game setup
        self.env = gym_super_mario_bros.make('SuperMarioBros-1-1-v1', render_mode='human', apply_api_compatibility=True)

        self.env = JoypadSpace(
            self.env,
            [['right'],
            ['right', 'A']]
        )

        self.env = SkipFrame(self.env, skip=4)
        #self.env = GrayScaleObservation(self.env, keep_dim=False) # for RL agent
        #self.env = ResizeObservation(self.env, shape=84) # for RL agent
        self.env = TransformObservation(self.env, f=lambda x: x / 255.)
        self.env = FrameStack(self.env, num_stack=1) #4

        # RL agent 
        #checkpoint = Path('src/gaming_slm/games/super_mario/trained_mario.chkpt')
        #self.mario = Mario(state_dim=(4, 84, 84), action_dim=self.env.action_space.n, save_dir='', checkpoint=checkpoint)
        #self.mario.exploration_rate = self.mario.exploration_rate_min

        self.jump_level = 0
        self.mario_loc_history = []

    def to_pil_image(self, image):
        # unwrap LazyFrames
        if LazyFrames is not None and isinstance(image, LazyFrames):
            image = np.array(image)

        # handle ndarray
        if isinstance(image, np.ndarray):
            image = np.squeeze(image)

            if image.dtype != np.uint8:
                image = (255 * image).clip(0, 255).astype(np.uint8)

            if image.ndim == 2:
                mode = "L"
            elif image.ndim == 3 and image.shape[2] == 3:
                mode = "RGB"
            else:
                raise ValueError(f"Unsupported ndarray shape: {image.shape}")

            return Image.fromarray(image, mode)

        # If it's already a PIL image
        if isinstance(image, Image.Image):
            return image

        raise TypeError(f"Unsupported image type: {type(image)}")
    
    # gamebench functions
    def initial_obs(self) -> Obs:
        self.env.reset()

        # skip meaningless init frames (for Mario level 1-1)
        n_skip = random.randint(20, 30)
        for i in range(n_skip):
            state, reward, done, trunc, info = self.env.step(action=0)
        self.env.render()

        obs = SuperMarioObs(
            state = {"image" : state},
            image = self.to_pil_image(state), #TODO: type check--- should be PIL image
            info = info,
            reward = {"distance": 0, "done": False}
        )
        return obs

    def get_game_info(self) -> dict:
        
        return {
            "past_mario_action": f"Jump Level {self.jump_level}",
            "mario_loc_history": f"{self.mario_loc_history[-3:]}"
        }

    def obs2text(self, obs: Obs) -> str:
        text = obs.to_text()
        return text

    def text2action(self, text: str) -> SuperMarioAction:
        if "Jump Level: " in text:
            jump_level = text.split("Jump Level: ")[1].strip()
            if jump_level in ['0', '1', '2', '3', '4', '5', '6']:
                self.jump_level = int(jump_level)
            print("jump_level: ", jump_level)
        else:
            print("***No 'Jump Level: ' in action_text!!!")
            
        return SuperMarioAction(values={"n_jumps": self.jump_level})

    def step(
        self, actions: SuperMarioAction
    ) -> Tuple[ObsType, SupportsFloat, bool, bool, Dict[str, Any]]:

        # Random Agent
        #p = 0.8
        #action = random.choices([0, 1], weights=[1-p, p])[0]
        #state, reward, done, trunc, info = self.env.step(action=action)

        # RL Agent
        #action = self.mario.act(self.prev_state)
        #state, reward, done, trunc, info = self.env.step(action=action)

        # Static Agent
        '''
        n_jumps = 6
        for i in range(n_jumps):
            state, reward, done, trunc, info = self.env.step(action=1)
            if done:
                break

            print("info['x_pos']: ", info['x_pos'])
            if info['x_pos'] > 1300 and info['x_pos'] <1340:
                break
            if info['x_pos'] > 2400 and info['x_pos'] <2410:
                break
            
        on_air = True
        mario_y_history = []
        while on_air and not done:
            state, reward, done, trunc, info = self.env.step(action=0)
            if done:
                break
            
            mario_y_history.append(info['y_pos'])
            if len(mario_y_history) >= 3:
                if mario_y_history[-3] == mario_y_history[-2] and mario_y_history[-2] == mario_y_history[-1]:
                    on_air = False
        '''

        # LLM Agent
        if actions.values['n_jumps'] == 0:
            state, reward, done, trunc, info = self.env.step(action=0)
        else:
            for i in range(actions.values['n_jumps']):
                state, reward, done, trunc, info = self.env.step(action=1)
                if done:
                    break
            
            on_air = True
            mario_y_history = []
            while on_air and not done:
                state, reward, done, trunc, info = self.env.step(action=0)
                if done:
                    break
                
                mario_y_history.append(info['y_pos'])
                if len(mario_y_history) >= 3:
                    if mario_y_history[-3] == mario_y_history[-2] and mario_y_history[-2] == mario_y_history[-1]:
                        on_air = False

        self.env.render()

        #time.sleep(1)

        obs = SuperMarioObs(
            state={"image": state},
            image = self.to_pil_image(state), #TODO: type check--- should be PIL image
            info=info,
            reward={"distance": info['x_pos'], "done": done}
        )
        self.mario_loc_history.append((info['x_pos'], info['y_pos']-34))

        return obs, info['x_pos'], done, trunc, info

    def evaluate(self, obs: SuperMarioObs):
        return obs.evaluate()