import logging
from dataclasses import dataclass

from mcp_agent_client.base_agent import BaseAgent
from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.utils.types.misc import Configurable

logger = logging.getLogger(__name__)


class MultiAgentRunner(Configurable):
    @dataclass
    class Config:
        max_steps: int

    cfg: Config

    def configure(self):
        self.max_steps = self.cfg.max_steps

    def set_agent(self, agent1: BaseAgent, agent2: BaseAgent):
        self.agent1 = agent1
        self.agent2 = agent2

    def set_env(self, env: BaseEnv):
        self.env = env


    def get_action(self, agent, obs, action, agent_id):
        if action is None or not action.actions:
            game_info = self.env.get_game_info(agent_id)
            text = agent(obs, game_info)
            action = self.env.text2action(text, agent_id)
            logger.info(f"Player {agent_id}'s action: {action}")
        return action
    
    def frame_step(self, obs1, obs2, action1, action2):
        action1 = self.get_action(self.agent1, obs1, action1, 1)
        action2 = self.get_action(self.agent2, obs2, action2, 2)

        obs1, obs2, reward, terminated, truncated, info = self.env.step(
            type(action1)([action1.actions[0]]), type(action2)([action2.actions[0]])
        )
        
        logger.info(f"Executing action of agent 1: {action1.actions[0]}")
        logger.info(f"Executing action of agent 2: {action2.actions[0]}")

        action1 = type(action1)(action1.actions[1:])
        action2 = type(action2)(action2.actions[1:])

        _, done = self.env.evaluate(obs1, obs2)

        return obs1, obs2, terminated | truncated | done, action1, action2

    def play(self):
        obs1, obs2 = self.env.initial_obs()
        action1, action2 = None, None

        for i in range(self.max_steps):
            logger.info(f"================ Frame step: {i+1}================")
            obs1, obs2, done, action1, action2 = self.frame_step(obs1, obs2, action1, action2)
            if done:
                score, _ = self.env.evaluate(obs1, obs2)
                break
        score, _ = self.env.evaluate(obs1, obs2)
        return score
