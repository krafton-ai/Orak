import os
import ast
import glob
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, List, Optional
from PIL import Image

from dacite import from_dict

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.gameio.window_capture import WindowCapture
from mcp_game_servers.stardew_valley.game.skill_registry import SkillRegistry
from mcp_game_servers.utils.types.game_io import Action, Obs


def safe_load_json(file_path, max_retries=5, delay=0.5):
    for i in range(max_retries):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            time.sleep(delay)

    raise RuntimeError(f"Failed to load JSON file: {file_path}")

def safe_write_json(file_path, content, max_retries=5, delay=0.5):
    for i in range(max_retries):
        try:
            with open(file_path, "w") as f:
                json.dump(content, f, indent=4)
                return
        except json.JSONDecodeError:
            time.sleep(delay)

    raise RuntimeError(f"Failed to load JSON file: {file_path}")


STATE_TEMPLATES = {
    "farm_cleanup": (
        "The player is located at coordinates {player.pos} of the {player.location}, and is facing {player.direction}. "
        "The coordinate system works as follows: +X is right, -X is left, +Y is down, and -Y is up. "
        "Important: The FarmHouse and Farm use different coordinate systems. The obstacle positions listed below are based on the Farm coordinate system. "
        "Obstacles in the Farm include:\n"
        "- Stones at positions {obstacles.stone}.\n"
        "- Weeds at positions {obstacles.weeds}.\n"
        "- Twigs at positions {obstacles.twig}.\n"
        "- Grass at positions {obstacles.grass}.\n"
        "- A tree at position {obstacles.tree}.\n"
        "The toolbar contains the following items:\n"
        "{toolbar_items}\n"
        "The selected item is the {toolbar.selected_item.name}, with a stack count of {toolbar.selected_item.stack}. "
    ),
    "cultivation": (
        "The player is located at coordinates {player.pos} of the {player.location}, and is facing {player.direction}. "
        "The coordinate system works as follows: +X is right, -X is left, +Y is down, and -Y is up. "
        "Important: The FarmHouse and Farm use different coordinate systems.\n"
        "Tilled soil is found at the following positions:\n"
        "{tilled_soil_info}\n"
        "The toolbar contains the following items:\n"
        "{toolbar_items}\n"
        "The selected item is the {toolbar.selected_item.name}, with a stack count of {toolbar.selected_item.stack}. "
    ),
    "shopping": (
        "The player is located at coordinates {player.pos} of the {player.location}, and is facing {player.direction}. "
        "The coordinate system works as follows: +X is right, -X is left, +Y is down, and -Y is up. "
        "Important: Different locations use different coordinate systems.\n\n"
        "{shop_info}"
        "The toolbar contains the following items:\n"
        "{toolbar_items}\n"
        "The selected item is the {toolbar.selected_item.name}, with a stack count of {toolbar.selected_item.stack}. "
    ),
    "earn_money": (
        "The player is located at {player.location}. "
        "The player has {player.money} gold and {player.energy}/50 energy remaining.\n\n"
        "Today is {world.season} {world.day}. {world.day_remaining} days remaining. The weather is {world.weather}.\n\n"
        "Crops currently growing:\n"
        "{crop_info}\n\n"
        # TODO: may have to add tilled soil (but no crops) info here
        "Number of empty tilled soil tiles:\n"
        "{world.num_empty_tilled_soil}\n\n"
        "The toolbar contains the following items:\n"
        "{toolbar_items}"
    ),
}


@dataclass
class Player:
    direction: str
    location: str
    pos: List[int]
    money: int
    energy: int


@dataclass
class Obstacle:
    crops: List[List[int]]
    grass: List[List[int]]
    stone: List[List[int]]
    tilled_soil: List[List[int]]
    tree: List[List[int]]
    twig: List[List[int]]
    weeds: List[List[int]]


@dataclass
class ShopItem:
    name: str
    price: int
    stock: int

@dataclass
class ToolbarItem:
    name: str
    stack: int
    type: str


@dataclass
class Toolbar:
    items: List[ToolbarItem]
    selected_item: ToolbarItem


@dataclass
class Crop:
    name: str
    stack: int
    days_to_harvest: int
    is_watered: bool

@dataclass
class World:
    day: int
    day_remaining: int
    season: str
    weather: str
    num_empty_tilled_soil: int

@dataclass
class StardewValleyObs(Obs):
    obstacles: Obstacle
    player: Player
    shop: Optional[List[ShopItem]]
    toolbar: Toolbar
    crops: List[Crop]
    world: World
    task_name: str
    image: Image.Image = None

    def format_toolbar_items(self) -> str:
        items = []
        for i, item in enumerate(self.toolbar.items, start=1):
            if item.name != "Empty":
                items.append(f"{i}. {item.name} (Stack: {item.stack})")
        return "\n".join(items)

    def format_tilled_soil(self) -> str:
        tilled_soil = self.obstacles.tilled_soil
        crops = self.obstacles.crops

        if not tilled_soil:
            return "No tilled soil found."

        soil_info = []
        for soil in tilled_soil:
            x, y, is_watered = soil
            water_status = "(Watered)" if is_watered == 1 else "(Not watered)"

            crop_info = "Parsnip seed not planted."
            for crop in crops:
                if crop[:2] == [x, y]:
                    growth_stage = crop[2]
                    if growth_stage == 4:
                        crop_info = "Parsnip seed planted and is fully grown."
                    else:
                        crop_info = f"Parsnip seed planted and is at growth stage {growth_stage}."

            soil_info.append(
                f"- Position [{x}, {y}] {water_status} ({crop_info})"
            )

        return "\n".join(soil_info)

    def format_shop_info(self) -> str:
        if self.shop is None:
            return "Shop menu is not opened.\n\n"

        shop_items = self.shop[:4]

        formatted_text = "Shop menu is opened.\nGame Shop Item List:\n\n"
        for shop_item in shop_items:
            formatted_text += f"- {shop_item.name}: {shop_item.price}G\n"

        return formatted_text

    def format_crop_info(self) -> str:
        crops = self.crops

        if not crops or len(crops) == 0:
            return "None."

        crop_info = []
        for crop in crops:
            crop_info.append(
                f"- {crop.name} (Stack: {crop.stack}, Days to harvest: {crop.days_to_harvest}, Watered: {crop.is_watered})"
            )

        return "\n".join(crop_info)

    def to_text(self):
        state_template = STATE_TEMPLATES[self.task_name]
        if self.task_name == "farm_cleanup":
            return state_template.format(
                player=self.player,
                obstacles=self.obstacles,
                toolbar=self.toolbar,
                toolbar_items=self.format_toolbar_items(),
            )
        elif self.task_name == "cultivation":
            return state_template.format(
                player=self.player,
                tilled_soil_info=self.format_tilled_soil(),
                toolbar=self.toolbar,
                toolbar_items=self.format_toolbar_items(),
            )
        elif self.task_name == "shopping":
            return state_template.format(
                player=self.player,
                shop_info=self.format_shop_info(),
                toolbar=self.toolbar,
                toolbar_items=self.format_toolbar_items(),
            )
        elif self.task_name == "earn_money":
            return state_template.format(
                player=self.player,
                crop_info=self.format_crop_info(),
                toolbar=self.toolbar,
                toolbar_items=self.format_toolbar_items(),
                world=self.world,
            )

    def evaluate(self):
        if self.task_name == "farm_cleanup":
            obstacles = self.obstacles
            num_obstacles = sum([len(v) for v in asdict(obstacles).values()])
            return 24 - num_obstacles, num_obstacles == 0

        elif self.task_name == "cultivation":
            toolbar_items = self.toolbar.items
            for item in toolbar_items:
                if item.name == "Parsnip":
                    return item.stack, True
            return 0, False

        elif self.task_name == "shopping":
            toolbar_items = self.toolbar.items
            for item in toolbar_items:
                if item.name == "Parsnip Seeds" and item.stack == 25:
                    return 1, True
            return 0, False
        
        elif self.task_name == "earn_money":
            return self.player.money, self.world.day == 14
        
        raise NotImplementedError


@dataclass
class StardewValleyAction(Action):
    values: List[str] = field(default_factory=list)

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __getitem__(self, index: int) -> int:
        return self.values[index]

    def __len__(self) -> int:
        return len(self.values)

    def to_json(self) -> str:
        return json.dumps(self.values)


class StardewValleyEnv(BaseEnv):
    @dataclass
    class Config:
        state_json_path: str
        action_json_path: str
        task: str
        log_path: str

        # skill_registry configuration
        skill_registry: dict

        input_modality: str = "text"

    cfg: Config

    def configure(self):
        if os.path.isdir(self.cfg.state_json_path):
            # If the path is a directory, append the most recent file
            self.state_json_path = sorted(
                glob.glob(os.path.join(self.cfg.state_json_path, "*.json"))
            )[-1]
            print("self.state_json_path: ", self.state_json_path)
        elif os.path.isfile(self.cfg.state_json_path):
            self.state_json_path = self.cfg.state_json_path
        self.action_json_path = self.cfg.action_json_path
        self.task = self.cfg.task
        self.input_modality = self.cfg.input_modality

        self.skill_registry = SkillRegistry(self.cfg.skill_registry)

        self.use_image = self.input_modality in ["image", "text_image"]
        if self.use_image:
            self.window_capture = WindowCapture(r"^Stardew Valley.*SMAPI.*mods", mode="dxcam")

        self.num_steps = 0

    def initial_obs(self) -> StardewValleyObs:
        state_json = safe_load_json(self.state_json_path)

        # modify crop to observation format
        crop_dict = {}

        for crop in state_json["crops"]:
            crop_key = (crop["name"], crop["days_to_harvest"], crop["is_watered"])
            if crop_key not in crop_dict:
                crop_dict[crop_key] = 1
            else:
                crop_dict[crop_key] += 1

        crop_dict = [{
            "name": k[0],
            "stack": crop_dict[k],
            "days_to_harvest": k[1],
            "is_watered": k[2],
        } for k in crop_dict]

        state_json["crops"] = crop_dict

        # calcuate remaining days
        state_json["world"]["day_remaining"] = 13 - state_json["world"]["day"]

        if self.use_image:
            image = self.window_capture.capture(log_path=self.cfg.log_path)
            state_json["image"] = image
        
        state_json["task_name"] = self.task

        obs = from_dict(StardewValleyObs, state_json)
        return obs

    def obs2text(self, obs: StardewValleyObs) -> str:
        return obs.to_text(self.task)

    def text2action(self, text: str) -> StardewValleyAction:
        text = text.replace("```python", "").replace("```", "")
        text = text.split("\n")

        text = [action for action in text if action]
        text = [
            action.split("#")[0] if "#" in action else action
            for action in text
        ]
        text = str(text)

        actions = ast.literal_eval(text)
        is_strange = (
            actions is None
            or len(actions) == 0
            or actions == ""
            or actions[0] == ""
        )
        if is_strange:
            return []
        return StardewValleyAction(values=actions)

    def get_game_info(self) -> dict:
        task_description = ""
        if self.task == "farm_cleanup":
            task_description = "The ground of the farm below the home is now scattered with various obstacles, including rocks, woods, trees, grasses and weeds. Get out of the house and move down and clear each obstacle one by one near the house."  # noqa
        elif self.task == "cultivation":
            task_description = "Cultivate and harvest a parsnip. Use your hoe to till the soil, then use a seed packet on the tilled soil to sow a crop. Water every day until the crop is ready for harvest."  # noqa
        elif self.task == "shopping":
            task_description = "The task is to move to shop, purchase 10 units of Parsnip Seeds and leave store. The shopkeeper is in left top corner and exit is in left bottom corner. Move to shop, purchase 10 units of Parsnip Seeds, and return home."  # noqa
        elif self.task == "earn_money":
            task_description = "Your task is to maximize profit before the morning of Spring 14th through strategical crop selection and cultivation. Each seed type has different growth times, purchase costs, and selling prices. 'Parsnip Seeds' grow in 4 days, costing 20g per seed and selling for 35g. 'Bean Starter' takes 10 days to mature, cost 60g per seed, sell for 40g, and can be harvested every 3 days after maturity. 'Cauliflower Seeds' take 12 days, cost 80g, and sell for 175g. 'Potato Seeds' grow in 6 days, cost 50g, sell for 80g, and have a 20% chance to yield an extra crop. When harvested, crops have a chance to be of higher quality, which can be sold for a better price. You have 50 energy per day, and tilling soil or watering seeds consumes 2 energy per action. If your energy drops below 0, you will become exhausted, starting the next day with only 26 energy. If your energy drops to -15, you will pass out, losing 10% of your money and starting the next day with 26 energy. Tilled soil without crop may revert to untilled soil overnight with a certain probability, requiring re-tilling before planting new seeds. Your final score is determined by the money you have at the start of Spring 14th. Any crops that are not harvested by that time will not be counted, even if they are still growing. Do not buy and plant seeds if the crop cannot fully mature within the remaining time. Doing so will yield no returns and result in wasted resources. Always check the growth time before planting. To succeed, you must choose the most profitable seeds, till the soil, plant and care for them daily, harvest when ready, and sell them—then repeat the process to grow your earnings. Other actions, such as clearing debris, are not required. Crop cultivation is the sole method of earning money."  # noqa
        
        def format_skill_list(functions):
            formatted_text = ""
            for func in functions:
                formatted_text += f"Function: {func['function_expression']}\n"
                formatted_text += f"Description: {func['description']}\n"
                formatted_text += "\n"
            return formatted_text

        return {
            "skill_library": format_skill_list(self.skill_registry.skill_library),
            "task_description": task_description,
        }

    def step(
        self, actions: StardewValleyAction
    ) -> tuple[StardewValleyObs, float, bool, bool, dict[str, Any]]:
        if self.num_steps != 0:
            self.skill_registry.io_env.key_press("esc")

        for skill in actions:
            try:
                skill_name, skill_params = (
                    self.skill_registry.convert_expression_to_skill(skill)
                )
            except ValueError as e:
                print(f"Error converting expression to skill: {e}")
                continue

            skill_dict = {"name": skill_name, "params": skill_params}
            safe_write_json(self.action_json_path, skill_dict)

            _ = self.skill_registry.execute_skill(
                skill_name=skill_name, skill_params=skill_params
            )
        self.num_steps += 1

        obs = self.initial_obs()
        self.skill_registry.io_env.key_press("esc")

        return obs, 0, False, False, {}

    def evaluate(self, obs: StardewValleyObs):
        return obs.evaluate()
