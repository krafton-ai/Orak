import argparse
import asyncio
from mcp_agent_servers.base_server import *

async def main():
    await server.run()

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

server = MCPAgentServer(
    args.config,
    expand_log_path=False if args.config != default_config_path else True
)

if __name__ == "__main__":
    asyncio.run(main())
