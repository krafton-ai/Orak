import logging
from dataclasses import dataclass
from typing import List
import os

from mcp_game_servers.utils.types.misc import Configurable
from mcp_game_servers.base_env import BaseEnv
from mcp_agent_client.base_agent import BaseAgent
from mcp_agent_client.base_client import MCPAgentClient
from mcp_agent_client.llms.llm import LocalBase
from mcp_agent_client.json_schemas import SCHEMA_REGISTRY
import omegaconf

logger = logging.getLogger(__name__)


class BaseRunner(Configurable):
    @dataclass
    class Config:
        max_steps: int

    cfg: Config

    def configure(self):
        self.max_steps = self.cfg.max_steps

    def set_agent(self, agent: BaseAgent):
        self.agent = agent
        if hasattr(self, "env") and self.env is not None:
            self._connect_agent_to_env()

    def set_env(self, env: BaseEnv):
        self.env = env
        if hasattr(self, "agent") and self.agent is not None:
            self._connect_agent_to_env()

    def _connect_agent_to_env(self):
        """
        Connect the environment instance to the agent, so the agent
        or its internal tools can access real-time state if needed.
        """
        self.agent.set_env_interface(self.env)

    def set_client(self, client: MCPAgentClient):
        self.client = client

    def step(self, obs):
        # FIXME: logger
        game_info = self.env.get_game_info()
        text = self.agent(obs, game_info)
        action = self.env.text2action(text)
        logger.info(f"executing actions: {action}")
        obs, reward, terminated, truncated, info = self.env.step(action)
        _, done = self.env.evaluate(obs)

        return obs, terminated | truncated | done

    def play(self):
        obs = self.env.initial_obs()

        for i in range(self.max_steps):
            logger.info(f"================step: {i+1}================")
            obs, done = self.step(obs)
            if done:
                break

        score, _ = self.env.evaluate(obs)

        return score, i+1
    
    async def mcp_play(self, game_server_path: str, agent_server_path: str, log_path: str, client_full_config: omegaconf.DictConfig):
        """
        Play the game with game and agent MCP servers.
        
        Args:
            game_server_path: Path to the game server script.
            agent_server_path: Path to the agent server script.
            log_path: Path to the log directory where server configs are stored.
            client_full_config: The full configuration object loaded by mcp_play_game.py.
        """
        # Connect to game and agent servers
        game_server_id = "_".join([os.path.basename(os.path.dirname(game_server_path)), "game_server"])
        agent_server_id = "_".join([os.path.basename(os.path.dirname(agent_server_path)), "agent_server"])
        
        game_server_config_path = os.path.join(log_path, "config_game.yaml")
        agent_server_config_path = os.path.join(log_path, "config_agent.yaml")

        await self.client.setup_server(game_server_path, game_server_id, game_server_config_path, client_full_config)
        await self.client.setup_server(agent_server_path, agent_server_id, agent_server_config_path, client_full_config)

        for i in range(self.max_steps):
            logger.info(f"================step: {i+1}================")
            
            # Get observations from game server
            obs_str, obs_image_str, game_info = await self.client.call_load_obs(game_server_id)

            # Add observation to memory
            await self.client.call_add_observation_to_memory(obs_str, obs_image_str, agent_server_id)

            # Process agent modules using agent server
            for module_type in self.agent.agent_modules:
                structured_output_kwargs = {}
                if module_type in self.agent.structured_output:
                    assert isinstance(self.agent.llm, LocalBase), "Structured output is currently tested for local models."

                    if "guided_regex" in self.agent.structured_output[module_type]:
                        structured_output_kwargs.update(self.agent.structured_output[module_type])
                    elif "guided_json" in self.agent.structured_output[module_type]:
                        json_schema = SCHEMA_REGISTRY[self.agent.structured_output[module_type]["guided_json"]]
                        structured_output_kwargs.update({"guided_json": json_schema})
                        structured_output_kwargs.update({"output_keys": self.agent.structured_output[module_type]["output_keys"]})

                system_prompt, user_prompt, images, call_chat_completion = await self.client.call_get_agent_module_prompts(
                    module_type, 
                    game_info,
                    agent_server_id
                )
                if system_prompt is None and user_prompt is None:
                    continue
                response, action_str = "", ""
                if call_chat_completion:
                    response = self.agent.chat_completion(system_prompt, user_prompt, images, **structured_output_kwargs)
                #logger.info(f"system_prompt: {system_prompt}\n\nuser_prompt: {user_prompt}\n\nresponse: {response}")
                action_str = await self.client.call_send_agent_module_response(response, agent_server_id, structured_output_kwargs)
                
            # Dispatch action to game server and check if game is finished
            assert action_str is not None
            score, done = await self.client.call_dispatch_final_action(action_str, game_server_id)
            if done:
                break

        await self.client.cleanup()
        return score, i+1
