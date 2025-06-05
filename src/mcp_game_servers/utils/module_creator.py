import importlib
from typing import Literal


def snake_to_camel(snake: str) -> str:
    """Convert snake_case to CamelCase"""
    name = snake.split("_")
    name = [word.capitalize() for word in name]
    name = "".join(name)
    return name


def camel_to_snake(camel: str) -> str:
    """Convert CamelCase to snake_case"""
    snake = [camel[0].lower()]
    for c in camel[1:]:
        if c.isupper():
            snake.append("_")
            snake.append(c.lower())
        else:
            snake.append(c)
    return "".join(snake)


def format_module_name(
    dirname: str,
    game_type: str,
) -> str:
    """Format module name"""
    PACKAGE_NAME = "mcp_game_servers"
    return f"{PACKAGE_NAME}.{game_type}.{dirname}"


def format_class_name(
    game_type: str, module_type: Literal["Env", "Agent", "Converter"]
) -> str:
    """Format class name"""
    return f"{game_type}{module_type}"


class ModuleCreator(object):
    """Module creator class"""

    def __init__(self, cfg):
        self.cfg = cfg

    def create(self):
        module_name = self.get_module_name()
        _module = importlib.import_module(module_name)
        class_name = self.get_class_name()
        _class = getattr(_module, class_name)
        _instance = _class(*self.get_args())
        return _instance

    def get_args(self) -> tuple:
        pass

    def get_module_name(self) -> str:
        pass

    def get_class_name(self) -> str:
        pass


class EnvCreator(ModuleCreator):
    """Environment creator class"""

    def get_args(self) -> list:
        return [self.cfg.env]

    def get_module_name(self) -> str:
        return format_module_name(
            game_type=camel_to_snake(self.cfg.env_name),
            dirname="game",
        )

    def get_class_name(self) -> str:
        return format_class_name(self.cfg.env_name, "Env")
