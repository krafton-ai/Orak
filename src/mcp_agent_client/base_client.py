import asyncio
import sys
import os
import json
import logging
import omegaconf
from typing import List, Tuple
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import base64
from PIL import Image
from io import BytesIO


logger = logging.getLogger(__name__)


class MCPAgentClient:
    def __init__(self):
        self.sessions = {}  # Dictionary to store multiple server sessions
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_script_path: str, server_id: str = None, config_path: str = None, client_full_config: omegaconf.DictConfig = None):
        """
        Connect to the MCP server by launching the server script as a subprocess.
        
        Args:
            server_script_path: Path to the MCP server script.
            server_id: Unique identifier for the server connection. If None, uses the script path as ID.
            config_path: Path to the configuration file for the server.
            client_full_config: The main client configuration object.
        """
        if server_id is None:
            server_id = os.path.basename(server_script_path)

        if server_id in self.sessions:
            raise ValueError(f"Server {server_id} is already connected")

        python_path = sys.executable
        current_command = python_path
        current_args = [server_script_path]
        if config_path:
            current_args.extend(["--config", config_path])

        if server_id == "street_fighter_game_server":
            if client_full_config and hasattr(client_full_config, 'diambra_settings'):
                rom_path = client_full_config.diambra_settings.get('rom_path')
                diambra_executable = client_full_config.diambra_settings.get('diambra_executable', 'diambra')

                if rom_path:
                    current_command = diambra_executable
                    diambra_args = ["run", "-r", rom_path, "python", server_script_path]
                    if config_path:
                        diambra_args.extend(["--config", config_path])
                    current_args = diambra_args
                    
                    logger.info(f"[MCPAgentClient] Using 'diambra run' for {server_id} from config. Command: {current_command}, Args: {current_args}")
                else:
                    logger.warning(f"[MCPAgentClient] 'rom_path' not found in diambra_settings for {server_id}. Falling back to standard python execution.")
            else:
                logger.warning(f"[MCPAgentClient] 'diambra_settings' not found in client_full_config for {server_id} or it's not a StreetFighter game server. Falling back to standard python execution.")
        
        server_params = StdioServerParameters(
            command=current_command,
            args=current_args,
            stderr=sys.stderr
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()

        response = await session.list_tools()
        tools = response.tools
        print(f"Connected to server \"{server_id}\" with tools:", [tool.name for tool in tools])

        self.sessions[server_id] = {
            'session': session,
            'stdio': stdio,
            'write': write
        }

    def str2image(self, img_str):
        img_data = base64.b64decode(img_str)
        loaded_image = Image.open(BytesIO(img_data))
        image = loaded_image.copy()
        loaded_image.close()
        return image

    def _parse_server_response(self, result, return_payload=False):
        try:
            payload = []
            for item in result:
                if item[0] == 'content':
                    for e in item[1]:
                        response_payload = e.text
                        # logger.info(f"response_payload: {response_payload}")
                        payload.append(response_payload)
            if return_payload:
                return payload
        except Exception as e:
            print("Error processing response:", e)

    def _get_payload(self, result):
        return json.loads(self._parse_server_response(result, return_payload=True)[0])

    async def setup_server(self, server_script_path: str, server_id: str = None, config_path: str = None, client_full_config: omegaconf.DictConfig = None):
        if not os.path.exists(server_script_path):
            raise FileNotFoundError(f"Server script not found at path: {server_script_path}")
            
        if sys.platform == 'win32':
            # print("Setting up binary mode for Windows")
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        try:
            await self.connect_to_server(server_script_path, server_id, config_path, client_full_config)
            # print("Server setup completed successfully")
        except Exception as e:
            print(f"Error during server setup: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            raise  # Re-raise the exception for proper error handling

    async def call_load_obs(self, server_id: str):
        if server_id not in self.sessions:
            raise ValueError(f"Server {server_id} is not connected")
        
        result = await self.sessions[server_id]['session'].call_tool("load-obs", None)
        payload = self._get_payload(result)
        return payload["obs_str"], payload["obs_image_str"], payload["game_info"]

    async def call_add_observation_to_memory(self, obs_str: str, obs_image_str: str, server_id: str):
        if server_id not in self.sessions:
            raise ValueError(f"Server {server_id} is not connected")
        
        result = await self.sessions[server_id]['session'].call_tool("add-observation-to-memory", {"obs_str": obs_str, "obs_image_str": obs_image_str})
        self._parse_server_response(result)

    async def call_dispatch_final_action(self, action_str: str, server_id: str) -> Tuple[int, bool]:
        if server_id not in self.sessions:
            raise ValueError(f"Server {server_id} is not connected")
            
        result = await self.sessions[server_id]['session'].call_tool("dispatch-final-action", {"action_str": action_str})
        payload = self._get_payload(result)
        return payload["score"], payload["is_finished"]

    async def call_list_agent_module_type(self, server_id: str) -> str:
        if server_id not in self.sessions:
            raise ValueError(f"Server {server_id} is not connected")
            
        result = await self.sessions[server_id]['session'].call_tool("list-agent-module-type", None)
        payloads = self._parse_server_response(result, return_payload=True)
        return payloads[0] if payloads else ""

    async def call_get_agent_module_prompts(self, module_type: str, game_info: dict, server_id: str) -> dict:
        if server_id not in self.sessions:
            raise ValueError(f"Server {server_id} is not connected")
            
        result = await self.sessions[server_id]['session'].call_tool("get-agent-module-prompts", {"module_type": module_type, "game_info": game_info})
        payload = self._get_payload(result)
        images = {k: self.str2image(v) for k, v in payload["image_strs"].items()}
        return payload["system_prompt"], payload["user_prompt"], images, payload["call_chat_completion"]

    async def call_send_agent_module_response(self, response: str, server_id: str, structured_output_kwargs: dict) -> dict:
        if server_id not in self.sessions:
            raise ValueError(f"Server {server_id} is not connected")
            
        result = await self.sessions[server_id]['session'].call_tool("send-agent-module-response", {"response": response, "structured_output_kwargs": structured_output_kwargs})
        payload = self._get_payload(result)
        return payload["parsed_output"]

    async def disconnect_server(self, server_id: str):
        """Disconnect a specific server"""
        if server_id in self.sessions:
            # The exit stack will handle cleanup of resources
            del self.sessions[server_id]

    async def cleanup(self):
        """Clean up all server connections"""
        self.sessions.clear()
        try:
            await asyncio.wait_for(self.exit_stack.aclose(), timeout=5)
        except asyncio.TimeoutError:
            print("[DEBUG] aclose() timed out — remaining callbacks in exit stack:")
        print("Clean up resources and close all sessions.")
