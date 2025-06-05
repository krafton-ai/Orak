import asyncio
import argparse
import logging
import os
import sys
import json
from datetime import datetime

from omegaconf import OmegaConf

from mcp_agent_client.runner.eval import BaseRunner
from mcp_agent_client.base_agent import BaseAgent
from mcp_agent_client.base_client import MCPAgentClient

logger = logging.getLogger(__name__)

def set_log_path(cfg):
    log_path = os.path.join(
                cfg.log_path,
                cfg.env_name,
                cfg.agent.llm_name,
                cfg.env.input_modality,
                cfg.agent.agent_type,
                datetime.now().strftime("%Y%m%d_%H%M%S")
            )
    cfg.log_path = log_path
    cfg.env.log_path = log_path
    cfg.agent.log_path = log_path
    os.makedirs(log_path, exist_ok=True)

    # Save the configuration to a file
    config_path = os.path.join(log_path, 'config_client.yaml')
    with open(config_path, 'w') as f:
        OmegaConf.save(config=cfg, f=f.name)

    # Create agent and game server configuration files
    agent_server_config_path = os.path.join(log_path, 'config_agent.yaml')
    agent_server_config = OmegaConf.create({
        "env_name": cfg.env_name,
        "log_path": cfg.log_path,
        "agent": cfg.agent,
    })
    with open(agent_server_config_path, 'w') as f:
        OmegaConf.save(config=agent_server_config, f=f.name)
    
    game_server_config_path = os.path.join(log_path, 'config_game.yaml')
    game_server_config = OmegaConf.create({
        "env_name": cfg.env_name,
        "log_path": cfg.log_path,
        "env": cfg.env,
    })
    with open(game_server_config_path, 'w') as f:
        OmegaConf.save(config=game_server_config, f=f.name)

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_path, 'client.log')),
            logging.StreamHandler()
        ]
    )

    def log_uncaught_exceptions(exctype, value, tb):
        logging.critical("Uncaught exception", exc_info=(exctype, value, tb))

    sys.excepthook = log_uncaught_exceptions

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


async def main():
    # uv run .\scripts\mcp_play_game.py  --config .\src\mcp_agent_client\configs\pwaat\config.yaml
    config = parse_configs()
    logger.info(config)
    runner = BaseRunner(config.runner)

    client = MCPAgentClient()
    runner.set_client(client)

    # load LLM agent
    llm_agent = BaseAgent(config.agent)
    runner.set_agent(llm_agent)

    # play with game and agent servers
    score, step = await runner.mcp_play(config.game_server, config.agent_server, config.env.log_path, config)

    # save result
    out_path = f"{config.env.log_path}/final_score.json"
    result = {
        "game": config.env_name,
        "llm": config.agent.llm_name,
        "agent_type": config.agent.agent_type,
        "task": config.env.task,
        "score": score,
        "final_step": step,
        "game_server": config.game_server,
        "agent_server": config.agent_server,
        "input_modality": config.env.input_modality,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    logger.info(f"Game: {config.env_name}")
    logger.info(f"LLM: {config.agent.llm_name}")
    logger.info(f"Agent: {config.agent.agent_type}")
    logger.info(f"Task: {config.env.task}")
    logger.info(f"Score: {score}")
    logger.info(f"Step: {step}")
    logger.info(f"Game Server: {config.game_server}")
    logger.info(f"Agent Server: {config.agent_server}")
    logger.info(f"Input Modality: {config.env.input_modality}")


if __name__ == "__main__":
    asyncio.run(main())
