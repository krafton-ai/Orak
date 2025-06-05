from dataclasses import dataclass
from typing import Any, Optional, Union

from omegaconf import DictConfig, OmegaConf


def parse_structured(
    fields: Any, cfg: Optional[Union[dict, DictConfig]] = None
) -> Any:
    scfg = OmegaConf.merge(OmegaConf.structured(fields), cfg)
    return scfg


class Configurable(object):
    @dataclass
    class Config:
        pass

    cfg: Config  # add this to every subclass to enable static type checking

    def __init__(
        self, cfg: Optional[Union[dict, DictConfig]] = None, *args, **kwargs
    ) -> None:
        self.cfg = parse_structured(self.Config, cfg)
        self.configure(*args, **kwargs)

    def configure(self, *args, **kwargs) -> None:
        raise NotImplementedError
