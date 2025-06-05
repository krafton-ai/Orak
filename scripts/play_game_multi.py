import argparse
import logging
import os
import json
from datetime import datetime

from omegaconf import OmegaConf

from mcp_agent_client.runner.multiagent_eval import MultiAgentRunner
from mcp_game_servers.utils.module_creator import EnvCreator
from mcp_agent_client.base_agent import BaselineAgent


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def set_log_path(cfg):
    log_path = os.path.join(
                cfg.log_path,
                cfg.env_name,
                cfg.agent1.llm_name,
                cfg.agent2.llm_name,
                cfg.agent1.agent_type,
                cfg.agent2.agent_type,
                datetime.now().strftime("%Y%m%d_%H%M%S")
            )
    cfg.env.log_path = log_path
    cfg.agent1.log_path = log_path
    cfg.agent2.log_path = log_path
    os.makedirs(log_path, exist_ok=True)

    return cfg

def parse_configs():
    # Define argparse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default="configs/star_craft/multi_gpt4o_gpt4omini.yaml"
    )
    args, unknown = parser.parse_known_args()

    # Load configuration file
    cfg = OmegaConf.load(args.config)

    # Override with command-line arguments
    cli_cfg = OmegaConf.from_cli(unknown)
    cfg = OmegaConf.merge(cfg, cli_cfg)

    # Set logging
    cfg = set_log_path(cfg)

    return cfg


def main():
    config = parse_configs()
    logger.debug(config)
    runner = MultiAgentRunner(config.runner)
    # setup Game_env
    env = EnvCreator(config).create()

    # load LLM agent
    llm_agent1 = BaselineAgent(config.agent1)
    llm_agent2 = BaselineAgent(config.agent2)
    runner.set_env(env)
    runner.set_agent(llm_agent1, llm_agent2)
    score = runner.play()

    # save result
    out_path = f"{config.env.log_path}/final_score.json"
    result = {
        "game": config.env_name,
        "llm1": config.agent1.llm_name,
        "agent_type1": config.agent1.agent_type,
        "llm2": config.agent2.llm_name,
        "agent_type2": config.agent2.agent_type,
        "score": score
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    logger.info(f"Game: {config.env_name}")
    logger.info(f"Agent1: {config.agent1.llm_name}")
    logger.info(f"Agent2: {config.agent2.llm_name}")
    logger.info(f"Score: {score}")


if __name__ == "__main__":
    main()
