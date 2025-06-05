import pkg_resources
import os
import gaming_slm.games.minecraft.voyager.utils as U


def load_control_primitives(primitive_names=None):
    if primitive_names is None:
        primitive_names = [
            primitives[:-3]
            for primitives in os.listdir(f"src/gaming_slm/games/minecraft/voyager/control_primitives")
            if primitives.endswith(".js")
        ]
    primitives = [
        U.load_text(f"src/gaming_slm/games/minecraft/voyager/control_primitives/{primitive_name}.js")
        for primitive_name in primitive_names
    ]
    return primitives
