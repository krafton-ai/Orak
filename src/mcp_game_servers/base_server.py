import sys
import os
import json
from datetime import datetime
from typing import Tuple
import omegaconf
import logging
import base64
from io import BytesIO

from mcp.server.fastmcp import FastMCP
from mcp_game_servers.utils.module_creator import EnvCreator

logger = logging.getLogger(__name__)


if sys.platform == 'win32':
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

def set_log_path(cfg, expand_log_path: bool = True) -> omegaconf.omegaconf.DictConfig:
    if expand_log_path:
        log_path = os.path.join(
            cfg.log_path,
            cfg.env_name,
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        cfg.env.log_path = log_path
        os.makedirs(log_path, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(cfg.log_path, 'game_server.log')),
            logging.StreamHandler()
        ],
        force=True
    )
    
    return cfg

class MCPGameServer:

    def __init__(self, mcp_server: FastMCP, config_path: str, expand_log_path: bool = True):
        self.cfg = self.create_config(config_path, expand_log_path)
        logger.info(f"config_path: {config_path}")
        self.mcp = mcp_server
        self.register_tools()

        # set env
        self.env = EnvCreator(self.cfg).create()

        # set temp var
        self.obs = None
        self.first_loading = True

    def create_config(self, config_path: str, expand_log_path: bool) -> omegaconf.omegaconf.DictConfig:
        cfg = omegaconf.OmegaConf.load(config_path)
        cfg = set_log_path(cfg, expand_log_path)
        return cfg

    def image2str(self, image):
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str

    def load_current_obs(self) -> Tuple[str, dict]:
        if self.first_loading:
            self.obs = self.env.initial_obs()
            self.first_loading = False
        obs_str, obs_image = self.obs.to_text(), getattr(self.obs, 'image', None)
        game_info = self.env.get_game_info()

        # encode image to base64
        if obs_image is not None:
            obs_image_str = self.image2str(obs_image)
        else:
            obs_image_str = ""
        return obs_str, obs_image_str, game_info

    def dispatch_action_and_get_score(self, action_str: str) -> Tuple[int, bool]:
        score = -1
        action = self.env.text2action(action_str)
        logger.info(f"executing actions: {action}")
        self.obs, reward, terminated, truncated, info = self.env.step(action)
        score, done = self.env.evaluate(self.obs)
        is_finished = terminated or truncated or done
        return score, is_finished

    def register_tools(self):
        @self.mcp.tool(name="load-obs", description="Load observation and game info from the server.")
        def load_obs() -> str:
            obs_str, obs_image_str, game_info = self.load_current_obs()
            logger.info(f"load_obs result: {obs_str}, \n{game_info}")
            return json.dumps({
                "obs_str": obs_str,
                "obs_image_str": obs_image_str,
                "game_info": game_info
            })

        @self.mcp.tool(name="dispatch-final-action", description="Dispatch a client final action to the server and return score and termination flag")
        def dispatch_final_action(action_str: str) -> str:
            score, is_finished = self.dispatch_action_and_get_score(action_str)
            logger.info(f"dispatch_final_action result: {score}, {is_finished}")
            return json.dumps({
                "score": score,
                "is_finished": is_finished
            })

    async def run(self):
        await self.mcp.run_stdio_async()
