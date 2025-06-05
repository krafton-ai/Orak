import argparse
import asyncio
from mcp_agent_servers.base_server import *
from mcp.server.fastmcp import FastMCP

'''
You are an AI defense attorney in an interactive Ace Attorney-style trial.

1. Utilize the available tools appropriately to play the game.

2. In each iteration, follow these steps:

    - Call load_obs to load the current game state from the server.

    - Then, call list_agent_module_type to check the names of the available agent modules, and sequentially invoke the ones that appear necessary for the current gameplay. You should call them in the order they are listed, but you may skip any that seem unnecessary.

    - For each agent call, use the get_agent_module_prompts function. Once you make the call, a prompt will be generated according to the specified format, and you must generate an answer following that format.

    - Send the generated answer to the server by calling send_agent_module_response, and retrieve the parsed_output. Use parsed_output as input for the next agent module call.

    - Finally, always call action_inference to obtain the final answer, then pass this value to dispatch_final_action so that your chosen input is applied in the game.

3. Once you complete these steps, the game will progress to the next iteration (next screen). Repeat the process starting with load_obs until you finish the game.
'''

async def main():
    await server.run()

server = FastMCP("agent-server")

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

    server = MCPAgentServer(
        server,
        args.config,
        expand_log_path=False if args.config != default_config_path else True
    )
    asyncio.run(main())
