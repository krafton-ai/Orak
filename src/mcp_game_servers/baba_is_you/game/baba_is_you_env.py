import ast
import json
import time
import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any, List, Tuple, Optional
from PIL import Image

from dacite import from_dict

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.gameio.window_capture import WindowCapture
from mcp_game_servers.utils.types.game_io import Action, Obs


def safe_load_json(file_path, task=None, max_retries=5, delay=0.5):
    if task:
        base_dir = os.path.dirname(os.path.expanduser(file_path))
        if base_dir.startswith("%APPDATA%"):
            base_dir = base_dir.replace("%APPDATA%", os.getenv("APPDATA"))
        sanitized_task = re.sub(r'[<>:"/\\|?*\s]+', '_', task)
        file_path = os.path.join(base_dir, f"state_{sanitized_task}.ba")
        state_key = f"state_{sanitized_task}"
    else:
        if file_path.startswith("%APPDATA%"):
            file_path = file_path.replace("%APPDATA%", os.getenv("APPDATA"))
        else:
            file_path = os.path.expanduser(file_path)
        state_key = None

    for i in range(max_retries):
        try:
            with open(file_path, "rb") as f:
                content = f.read().decode('utf-8')

                if state_key:
                    key_start = content.find(f"{state_key}=")
                    if key_start == -1:
                        print(f"State key '{state_key}' not found in file")
                        return None

                    brace_start = content.find('{', key_start)
                    if brace_start == -1:
                        print(f"Opening brace not found after state key '{state_key}'")
                        return None

                    brace_count = 1
                    json_end = brace_start + 1

                    for i in range(brace_start + 1, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break

                    if json_end > brace_start + 1:
                        try:
                            json_content = content[brace_start:json_end]
                            return json.loads(json_content)
                        except json.JSONDecodeError as e:
                            print(f"Failed to parse JSON: {e}")
                            time.sleep(delay)
                    else:
                        print("Could not find closing brace for JSON content")
                        return None
                else:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        time.sleep(delay)

        except FileNotFoundError:
            print(f"File not found: {file_path}")
            if task:
                return safe_load_json(os.path.join(os.path.dirname(file_path), "new.ba"), None, max_retries, delay)
            return None

    raise RuntimeError(f"Failed to load JSON file: {file_path}")


STATE_TEMPLATE = (
    "Level: {level_info.name}\n"
    "Dimensions: {adjusted_width}x{adjusted_height} (max x: {max_x}, max y: {max_y})\n\n"
    "Objects:\n"
    "{objects_info}\n\n"
    "Active Rules:\n"
    "{active_rules}"
)


@dataclass
class LevelInfo:
    name: str
    width: int
    height: int


@dataclass
class Position:
    x: int
    y: int


@dataclass
class GameObject:
    type: str
    name: str
    position: Position


@dataclass
class BabaIsYouObs(Obs):
    level_info: LevelInfo
    objects: List[GameObject]
    image: Image.Image = None

    def parse_rules(self) -> dict[str, set[str]]:
        from collections import defaultdict

        text_map = {}
        for obj in self.objects:
            if obj.type == 'text':
                text_map[(obj.position.x, obj.position.y)] = obj.name.lower()

        rules = defaultdict(set)

        def check_line(x: int, y: int, dx: int, dy: int):
            word1 = text_map.get((x, y))
            word2 = text_map.get((x + dx, y + dy))
            word3 = text_map.get((x + 2*dx, y + 2*dy))
            if word1 and word2 == "is" and word3:
                rules[word1].add(word3)

        for (x, y) in text_map.keys():
            check_line(x, y, 1, 0)
            check_line(x, y, 0, 1)

        return rules

    def format_objects_info(self) -> str:
        objects_by_type = {}
        for obj in self.objects:
            key = f"{obj.type}:{obj.name}"
            if key not in objects_by_type:
                objects_by_type[key] = []
            objects_by_type[key].append((f"x:{obj.position.x}", f"y:{obj.position.y}"))
        
        return "\n".join([
            f"- {key}: at positions [{', '.join(f'(x:{x[2:]}, y:{y[2:]})' for x,y in positions)}]"
            for key, positions in objects_by_type.items()
        ])

    def format_active_rules(self) -> str:
        """Format the active rules in a more readable way."""
        rules = self.parse_rules()
        if not rules:
            return "No active rules found."
            
        formatted_rules = []
        for subject, properties in rules.items():
            for prop in properties:
                formatted_rules.append(f"{subject.upper()} IS {prop.upper()}")
                
        return "\n".join(sorted(formatted_rules))

    def to_text(self) -> str:
        adjusted_width = self.level_info.width - 2
        adjusted_height = self.level_info.height - 2
        
        max_x = self.level_info.width - 3
        max_y = self.level_info.height - 3
        
        return STATE_TEMPLATE.format(
            level_info=self.level_info,
            adjusted_width=adjusted_width,
            adjusted_height=adjusted_height,
            max_x=max_x,
            max_y=max_y,
            objects_info=self.format_objects_info(),
            active_rules=self.format_active_rules()
        )

    def evaluate(self, current_turn: int) -> Tuple[float, bool]:
        rules = self.parse_rules()

        # 1) Level cleared?
        you_objects = []
        win_objects = []
        for obj in self.objects:
            if obj.type == 'text':
                continue
            props = rules.get(obj.name.lower(), set())
            if 'you' in props:
                you_objects.append(obj)
            if 'win' in props:
                win_objects.append(obj)

        for y in you_objects:
            for w in win_objects:
                if y.position.x == w.position.x and y.position.y == w.position.y:
                    return 100.0, True

        # 2) Any “<something> IS WIN” rule?
        if any('win' in props for props in rules.values()):
            return 40.0, False

        # 3) “WALL IS STOP” broken?
        if 'stop' not in rules.get('wall', set()):
            return 20.0, False

        return 0.0, False


@dataclass
class BabaIsYouAction(Action):
    VALID_DIRECTIONS = ["idle", "left", "right", "up", "down"]
    movements: List[Tuple[str, int]] = None  # List of (direction, steps) tuples
    
    def __post_init__(self):
        if self.movements is None:
            self.movements = [("idle", 1)]
        else:
            # Validate and clean movements
            valid_movements = []
            for direction, steps in self.movements:
                if direction not in self.VALID_DIRECTIONS:
                    direction = "idle"
                if steps < 1:
                    steps = 1
                valid_movements.append((direction, steps))
            self.movements = valid_movements if valid_movements else [("idle", 1)]
    
    @classmethod
    def from_string(cls, action_str: str) -> "BabaIsYouAction":
        action_str = ' '.join(part.split('(')[0].strip() for part in action_str.split('\n'))
        parts = action_str.strip().strip('"`\'').lower().split()
        movements = []
        
        i = 0
        while i < len(parts):
            direction = parts[i]
            if direction not in cls.VALID_DIRECTIONS:
                direction = "idle"
                
            steps = 1
            if i + 1 < len(parts):
                try:
                    steps_val = int(parts[i + 1])
                    if steps_val > 0:
                        steps = steps_val
                        i += 2
                        movements.append((direction, steps))
                        continue
                except ValueError:
                    pass
            i += 1
            movements.append((direction, steps))
            
        return cls(movements=movements if movements else [("idle", 1)])
    
    def to_json(self) -> str:
        return json.dumps({"movements": self.movements})
    
    def to_str(self) -> str:
        if not self.movements or self.movements[0][0] == "idle":
            return "idle"
        
        parts = []
        for direction, steps in self.movements:
            if steps == 1:
                parts.append(direction)
            else:
                parts.append(f"{direction} {steps}")
        return " ".join(parts)


class BabaIsYouEnv(BaseEnv):
    @dataclass
    class Config:
        log_path: str
        state_json_path: str
        task: Optional[str] = None
        input_modality: str = "text"
    
    cfg: Config
    current_turn: int = 0

    def configure(self):
        self.state_json_path = self.cfg.state_json_path
        self.task = self.cfg.task
        self.input_modality = self.cfg.input_modality
        self.current_turn = 0

        self.use_image = self.input_modality in ["image", "text_image"]
        if self.use_image:
            self.window_capture = WindowCapture(r"^Baba Is You$", mode="bitblt")

    def initial_obs(self) -> BabaIsYouObs:
        state_json = safe_load_json(self.state_json_path, self.task)
        if state_json is None:
            raise RuntimeError(f"Failed to load initial state for level: {self.task}. Check if the file exists at the expected location.")
        if self.use_image:
            image = self.window_capture.capture(log_path=self.cfg.log_path)
            state_json["image"] = image
        obs = from_dict(BabaIsYouObs, state_json)
        return obs

    def obs2text(self, obs: BabaIsYouObs) -> str:
        return obs.to_text()
    
    def text2action(self, text: str) -> "BabaIsYouAction":
        return BabaIsYouAction.from_string(text)
    
    def get_game_info(self) -> dict:
        return {
        }
    
    def step(self, actions: BabaIsYouAction) -> tuple[BabaIsYouObs, float, bool, bool, dict[str, Any]]:
        self.current_turn += 1
        
        from mcp_game_servers.gameio.io_env import IOEnvironment
        class SimpleConfig:
            def __init__(self):
                self.env_resolution = (1920, 1080)
                self.env_region = (0, 0, 1920, 1080)
                self.env_name = "Baba Is You"
                self.win_name_pattern = "^Baba Is You$"
        
        config = SimpleConfig()
        io_env = IOEnvironment(config)
        
        windows = io_env.get_windows_by_config()
        if not windows:
            raise RuntimeError("Could not find Baba Is You window")
        
        window = windows[0]
        window.activate()
        time.sleep(0.3)
        
        action_key_map = {
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
            "idle": None
        }
        
        for direction, steps in actions.movements:
            key = action_key_map.get(direction)
            if key:
                for _ in range(steps):
                    io_env.key_press(key, duration=0.02)
                    time.sleep(0.6)
                    
                    # Load the current state after each step
                    state = safe_load_json(self.cfg.state_json_path, self.cfg.task)
                    if state is None:
                        raise RuntimeError("Failed to load state after action")
                    
                    # Convert state to observation
                    obs = from_dict(data_class=BabaIsYouObs, data=state)
                    
                    # Check if we've won or lost
                    reward, done = obs.evaluate(self.current_turn)
                    if done:
                        return obs, reward, done, False, {}
        
        # Load final state after all movements
        state = safe_load_json(self.cfg.state_json_path, self.cfg.task)
        if state is None:
            raise RuntimeError("Failed to load state after action")
        if self.use_image:
            image = self.window_capture.capture(log_path=self.cfg.log_path)
            state["image"] = image
        
        obs = from_dict(data_class=BabaIsYouObs, data=state)
        reward, done = obs.evaluate(self.current_turn)
        
        return obs, reward, done, False, {}
    
    def evaluate(self, obs: BabaIsYouObs):
        return obs.evaluate(self.current_turn)