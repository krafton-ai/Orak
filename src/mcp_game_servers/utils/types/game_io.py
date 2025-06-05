from abc import ABC
from dataclasses import dataclass


@dataclass
class Obs(ABC):
    pass


@dataclass
class Action(ABC):
    pass
