import argparse
import asyncio
from mcp_game_servers.base_server import *
from mcp.server.fastmcp import FastMCP

async def main():
    await server.run()

server = FastMCP("game-server")

if __name__ == "__main__":
    default_config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "config.yaml"
    )

    # Define argparse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default=default_config_path,
    )
    args = parser.parse_args()

    server = MCPGameServer(
        server,
        args.config,
        expand_log_path=False if args.config != default_config_path else True
    )
    asyncio.run(main())
