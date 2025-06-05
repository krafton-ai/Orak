import argparse
import logging
import os
import json
from datetime import datetime

from omegaconf import OmegaConf

from mcp_agent_client.runner.eval import BaseRunner
from mcp_game_servers.utils.module_creator import EnvCreator
from mcp_agent_client.base_agent import BaselineAgent


logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)


def set_log_path(cfg):
    log_path = os.path.join(
                cfg.log_path,
                cfg.env_name,
                cfg.agent.llm_name,
                cfg.env.input_modality,
                cfg.agent.agent_type,
                datetime.now().strftime("%Y%m%d_%H%M%S")
            )
    cfg.env.log_path = log_path
    cfg.agent.log_path = log_path
    os.makedirs(log_path, exist_ok=True)

    config_path = os.path.join(log_path, 'config.yaml')
    with open(config_path, 'w') as f:
        OmegaConf.save(config=cfg, f=f.name)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_path, 'run.log')),
            logging.StreamHandler()
        ]
    )

    return cfg

def parse_configs():
    # Define argparse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default="configs/star_craft/play_full_game.yaml"
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
    runner = BaseRunner(config.runner)
    # setup Game_env
    env = EnvCreator(config).create()

    # load LLM agent
    llm_agent = BaselineAgent(config.agent)
    logger.info(f"Input_modality: {config.env.input_modality}")
    logger.info(f"Agent_type: {config.agent.agent_type}")
    runner.set_env(env)
    runner.set_agent(llm_agent)
    score, step = runner.play()

    # save result
    out_path = f"{config.env.log_path}/final_score.json"
    result = {
        "game": config.env_name,
        "llm": config.agent.llm_name,
        "agent_type": config.agent.agent_type,
        "task": config.env.task,
        "score": score,
        "final_step": step,
        "input_modality": config.env.input_modality
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    logger.info(f"Game: {config.env_name}")
    logger.info(f"LLM: {config.agent.llm_name}")
    logger.info(f"Agent: {config.agent.agent_type}")
    logger.info(f"Task: {config.env.task}")
    logger.info(f"Score: {score}")
    logger.info(f"Step: {step}")
    logger.info(f"Input Modality: {config.env.input_modality}")


if __name__ == "__main__":
    main()
