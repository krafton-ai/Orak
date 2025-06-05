import os
import yaml
from typing import Dict, Any

def load_config(base_config_path: str, additional_config_paths: list[str]) -> Dict[str, Any]:
    """
    Loads and merges multiple config files.
    
    Args:
        base_config_path: Path to the base config file
        additional_config_paths: List of paths to additional config files to merge
    
    Returns:
        Dictionary containing the merged configuration
    """
    def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merges two dictionaries."""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    # Load base config file
    with open(base_config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Load and merge additional config files
    for config_path in additional_config_paths:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                additional_config = yaml.safe_load(f)
                if additional_config:
                    config = deep_merge(config, additional_config)

    return config

def get_merged_config(game_name: str) -> Dict[str, Any]:
    """
    Loads and merges all config files for a specific game.
    
    Args:
        game_name: Name of the game (e.g., 'pwaat', 'twenty_fourty_eight')
    
    Returns:
        Dictionary containing the merged configuration
    """
    base_config_path = os.path.join('src', 'mcp_agent_client', 'configs', game_name, 'config.yaml')
    additional_configs = [
        os.path.join('src', 'mcp_agent_servers', game_name, 'config.yaml'),
        os.path.join('src', 'mcp_game_servers', game_name, 'config.yaml')
    ]
    
    return load_config(base_config_path, additional_configs)

if __name__ == '__main__':
    # Test code
    # PWAAT game config test
    pwaat_config = get_merged_config('pwaat')
    print("PWAAT Merged Config:")
    print(yaml.dump(pwaat_config, default_flow_style=False))
    
    # 2048 game config test (if config files exist)
    twenty_fourty_eight_config = get_merged_config('twenty_fourty_eight')
    print("\n2048 Merged Config:")
    print(yaml.dump(twenty_fourty_eight_config, default_flow_style=False))
