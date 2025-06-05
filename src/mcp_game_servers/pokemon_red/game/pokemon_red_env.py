import subprocess
import socket
import time
from datetime import datetime

import os
import re
from dataclasses import dataclass
import importlib.util
from PIL import Image

import threading
from pyboy import PyBoy
from pyboy.utils import WindowEvent

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.utils.types.game_io import Action, Obs
from mcp_game_servers.pokemon_red.game.pyboy_runner import PyBoyRunner


@dataclass
class PokemonRedObs(Obs):
    state_text: str
    terminated: bool = False
    image: Image.Image = None

    def to_text(self) -> str:
        return self.state_text
    def set_text(self, state_text):
        self.state_text = state_text

@dataclass
class PokemonRedAction(Action):
    action: str

    def to_json(self) -> str:
        return self.action


class PokemonRedEnv(BaseEnv):
    @dataclass
    class Config:
        log_path: str
        task: str
        rom_path: str
        success_condition: str
        exp_name: str
        input_modality: str = "text"

    cfg: Config

    def configure(self):

        self.log_path = self.cfg.log_path
        self.task = self.cfg.task
        self.rom_path = self.cfg.rom_path
        self.success_condition = self.cfg.success_condition
        self.score = 0

        self.running = True
        self.pending_action = None

        self.runner = PyBoyRunner(self.rom_path)

        self.exp_name = self.cfg.exp_name

        self._start_game()

        self.prev_state_text = ""
        self.state_text = ""
        self.prev_state_dict = {}
        self.state_dict = {}

        self.map_flag, self.ball_flag, self.catch_flag, self.pewter_flag, self.leader_flag = False, False, False, False, False

    def _start_game(self):
        # === Execute mGBA (with Lua script) ===
        print("[Python] Launching PyBoy...")
        
        # PyBoy game loop in SubThread
        game_thread = threading.Thread(target=self.runner.tick_loop, daemon=True)
        game_thread.start()
        
        time.sleep(5)
        
    def _send_action(self, action):
        # self.sock.sendall((action + "\n").encode())
        self.runner.send_input(action.lower())

    def _receive_state(self):
        # data = self.sock.recv(4096).decode()
        data = self.runner.get_state()

        return data
    
    def parse_game_state(self, text):
        result = {}

        # 1. State
        state_match = re.search(r"State:\s*(\w+)", text)
        result['state'] = state_match.group(1) if state_match else None

        # 2. Filtered Screen Text
        filtered_text = re.search(r"\[Filtered Screen Text\]\n(.*?)(?=\[Selection Box Text\])", text, re.DOTALL)
        text_tmp = filtered_text.group(1).strip()
        result['filtered_screen_text'] = text_tmp if text_tmp != "" else "N/A"

        # 3. Selection Box Text
        selection_box = re.search(r"\[Selection Box Text\]\n(.*?)(?=\[Enemy Pokemon\])", text, re.DOTALL)
        text_tmp = selection_box.group(1).strip()
        result['selection_box_text'] = text_tmp if text_tmp != "" else "N/A"

        # 4. Enemy Pokemon
        enemy_pokemon = {}
        enemy_section = re.search(r"\[Enemy Pokemon\]\n(.*?)(?=\[Current Party\])", text, re.DOTALL)
        if enemy_section:
            for line in enemy_section.group(1).splitlines():
                if ": " in line:
                    key, value = line.split(": ", 1)
                    enemy_pokemon[key.strip()] = value.strip()
        result['enemy_pokemon'] = enemy_pokemon

        # 5. Your Party
        party_match = re.search(r"\[Current Party\]\n(.*?)(?=\[Badge List\])", text, re.DOTALL)
        result['your_party'] = party_match.group(1).strip() if party_match else ""

        # 6. Badge List
        badge_match = re.search(r"\[Badge List\]\n(.*?)(?=\[Bag\])", text, re.DOTALL)
        result['badge_list'] = badge_match.group(1).strip() if badge_match else ""

        # 7. Inventory
        inventory_match = re.search(r"\[Bag\]\n(.*?)(?=\[Current Money\])", text, re.DOTALL)
        result['inventory'] = inventory_match.group(1).strip() if inventory_match else ""

        # 8. Current Money
        money_match = re.search(r"\[Current Money\]:\s*¥(\d+)", text)
        result['money'] = int(money_match.group(1)) if money_match else 0

        # 9. Map Info
        map_info = {}
        map_section = re.search(r"\[Map Info\]\n(.*)", text, re.DOTALL)
        if map_section:
            map_text = map_section.group(1)
            map_name_match = re.search(r"Map Name:\s*(.*?),", map_text)
            map_info['map_name'] = map_name_match.group(1) if map_name_match else None

            map_type_match = re.search(r"Map type:\s*(.*)", map_text)
            map_info['map_type'] = map_type_match.group(1).strip() if map_type_match else None

            expansion_match = re.search(r"Expansion direction:\s*(.*)", map_text)
            map_info['expansion_direction'] = expansion_match.group(1).strip() if expansion_match else None

            coords_match = re.search(r"\(x_max , y_max\):\s*\((\d+),\s*(\d+)\)", map_text)
            map_info['x_max'] = int(coords_match.group(1)) if coords_match else None
            map_info['y_max'] = int(coords_match.group(2)) if coords_match else None

            pos_match = re.search(r"Your position \(x, y\): \((\d+), (\d+)\)", map_text)
            map_info['player_pos_x'] = int(pos_match.group(1)) if pos_match else None
            map_info['player_pos_y'] = int(pos_match.group(2)) if pos_match else None

            facing_match = re.search(r"Your facing direction:\s*(\w+)", map_text)
            map_info['facing'] = facing_match.group(1) if facing_match else None

            try:
                # Optional: extract action instructions and screen map
                map_info['map_screen_raw'] = re.search(r"Map on Screen:\n(.+)", map_text, re.DOTALL).group(1).strip()
            except:
                map_info['map_screen_raw'] = None

        result['map_info'] = map_info

        return result
    
    def initial_obs(self) -> Obs:
        state_text = self._receive_state()
        self.state_text = state_text
        self.state_dict = self.parse_game_state(self.state_text)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        image = self.runner.take_screenshot(dir_name=os.path.join(self.log_path, 'screenshots'), img_name=f'screenshot_{timestamp}.png')
        return PokemonRedObs(state_text=state_text, image=image)

    def obs2text(self, obs: Obs) -> str:
        return obs.to_text()

    def text2action(self, text: str) -> Action:
        return PokemonRedAction(action=text.strip())
    
    def send_action_set(self, commands):
        if commands == [] or commands == None:
            self._send_action('pass')
            time.sleep(0.1)
            return
        
        for action in commands:
            if action not in ['up', 'down', 'left', 'right', 'a', 'b', 'start', 'select', 'none', 'quit']:
                self._send_action('pass')
                time.sleep(0.1)
                return
            self._send_action(action)
            time.sleep(0.1)
        
    def step(self, action: Action):
        actions = action.action.strip("'\"").lower()
        commands = re.split(r'[|/;, \t\n]+', actions)

        self.send_action_set(commands)

        time.sleep(3)
        state_text = self._receive_state()

        self.prev_state_text = self.state_text
        self.prev_state_dict = self.state_dict
        self.state_text = state_text
        self.state_dict = self.parse_game_state(self.state_text)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        image = self.runner.take_screenshot(dir_name=os.path.join(self.log_path, 'screenshots'), img_name=f'screenshot_{timestamp}.png')
        obs = PokemonRedObs(state_text=state_text, image=image)
        reward, terminated, truncated, info = 0, False, False, {}
        return obs, reward, terminated, truncated, info
    
    def evaluate(self, obs:Obs):
        if self.score == 0:
            if (self.prev_state_dict['map_info']['map_name'] != self.state_dict['map_info']['map_name']) and (not 'RedsHouse' in self.state_dict['map_info']['map_name']):
                self.score += 1
        elif self.score == 1:
            if 'SPRITE_OAK' in self.state_dict['map_info']['map_screen_raw']:
                self.score += 1
        elif self.score == 2:
            if 'Name' in self.state_dict['your_party']:
                self.score += 1
        elif self.score == 3:
            if (self.prev_state_dict['state'] != self.state_dict['state']) and 'Battle' in self.prev_state_dict['state']:
                self.score += 1
        elif self.score == 4:
            if 'Viridian' in self.state_dict['map_info']['map_name']:
                self.score += 1
        elif self.score == 5:
            if "OAK's PARCEL" in self.state_dict['inventory']:
                self.score += 1
        elif self.score == 6:
            if not "OAK's PARCEL" in self.state_dict['inventory']:
                self.score += 1
        elif self.score > 6:
            if not self.map_flag and "TOWN MAP" in self.state_dict['inventory']:
                self.score += 1
                self.map_flag = True
            if not self.ball_flag and "BALL" in self.state_dict['inventory']:
                self.score += 1
                self.ball_flag = True
            if not self.catch_flag and '\nName' in self.state_dict['your_party']:
                self.score += 1
                self.catch_flag = True
            if not self.pewter_flag and "Pewter" in self.state_dict['map_info']['map_name']:
                self.score += 1
                self.pewter_flag = True
            if not self.leader_flag and "Boulder" in self.state_dict['badge_list']:
                self.score += 1
                self.leader_flag = True

        if self.score == 12 or self.runner.quit_flag:
            done = True
        else:
            done = False

        return f'{self.score/12*100:.1f} ({self.score}/12)', done

    def get_game_info(self) -> dict:
        return {

        }

    def close(self):
        self.running = False
        self.pyboy.stop()
        if hasattr(self, "tick_thread") and self.tick_thread.is_alive():
            self.tick_thread.join(timeout=1)
