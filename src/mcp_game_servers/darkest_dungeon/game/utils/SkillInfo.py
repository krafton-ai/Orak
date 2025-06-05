from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import os
import re

@dataclass
class SkillLevelInfo:
    level: int
    type: str
    atk: str
    dmg: str
    crit: str
    launch: str
    target: str
    is_crit_valid: bool
    effects: List[str]
    is_stall_invalidating: bool = False
    self_target_valid: bool = True
    heal: Optional[str] = None
    move: Optional[str] = None
    per_battle_limit: Optional[int] = None

    def get_launch_ranks(self) -> Set[int]:
        """Parse launch pattern to get ranks the skill can be used from.
        Example: '321' means can be used from ranks 3, 2, 1"""
        return {int(c) for c in self.launch}

    def get_target_ranks(self) -> Set[int]:
        """Parse target pattern to get ranks the skill can target.
        Example: '12' means can target one enemy from ranks 1 or 2
        Special cases:
        - '~12' means can target all enemies in ranks 1 AND 2
        - '@12' means can target allies in ranks 1 or 2
        - '@~12' means can target ALL allies in ranks 1 AND 2
        - '0' or empty means self-targeting"""
        if not self.target or self.target == '0':
            return {0}  # Special case for self-targeting skills
        
        # Remove special characters and parse numbers
        clean_target = self.target.lstrip('@~')
        ranks = {int(c) for c in clean_target}
        
        # Handle ally targeting
        if self.target.startswith('@'):
            if self.target.startswith('@~'):
                return ranks  # Can target ALL allies in specified ranks
            return ranks  # Can target allies in specified ranks
        
        # Handle enemy targeting
        if self.target.startswith('~'):
            return ranks  # Can target all enemies in ALL specified ranks
        return ranks  # Can target one enemy from any of the specified ranks

    def get_move_info(self) -> tuple[int, int]:
        """Parse move pattern to get movement values.
        Returns (backward_moves, forward_moves)"""
        if not self.move:
            return (0, 0)
        moves = self.move.split()
        if len(moves) != 2:
            return (0, 0)
        return (int(moves[0]), int(moves[1]))

    def get_heal_range(self) -> Optional[tuple[int, int]]:
        """Parse heal pattern to get healing range.
        Returns (min_heal, max_heal) or None if no healing"""
        if not self.heal:
            return None
        heals = self.heal.split()
        if len(heals) != 2:
            return None
        return (int(heals[0]), int(heals[1]))

    def is_ally_targeting(self) -> bool:
        """Check if this skill targets allies"""
        return self.target.startswith('@')

    def is_healing_skill(self) -> bool:
        """Check if this skill has healing capabilities"""
        return self.heal is not None or any(effect.startswith('heal') for effect in self.effects)

class SkillInfo:
    def __init__(self, id: str):
        self.id = id
        self.levels: Dict[int, SkillLevelInfo] = {}

    def add_level(self, level_info: SkillLevelInfo):
        # Only add if this level doesn't exist yet
        if level_info.level not in self.levels:
            self.levels[level_info.level] = level_info
        else:
            print(f"Warning: Duplicate level {level_info.level} found for skill {self.id}")

    def get_level_info(self, level: int) -> Optional[SkillLevelInfo]:
        return self.levels.get(level)

class SkillInfoParser:
    def __init__(self, game_install_location: str):
        self.game_install_location = game_install_location
        self.skill_info_cache: Dict[str, Dict[str, SkillInfo]] = {}

    def parse_skill_line(self, line: str) -> Optional[tuple[str, SkillLevelInfo]]:
        """Parse a single combat_skill line from .info.darkest file"""
        if not line.startswith("combat_skill:"):
            return None

        # Extract all key-value pairs with improved pattern
        pattern = r'\.(\w+)\s+"?([^"\s]+)"?'
        matches = re.findall(pattern, line)
        if not matches:
            print(f"Warning: No matches found in line: {line}")
            return None

        # Convert matches to dict
        attrs = dict(matches)
        
        # Parse effects
        effects = []
        if "effect" in attrs:
            effects = attrs["effect"].split(" ")

        # Ensure required attributes have default values
        skill_id = attrs.get("id", "")
        level = int(attrs.get("level", 0))
        type_ = attrs.get("type", "")
        atk = attrs.get("atk", "0%")
        dmg = attrs.get("dmg", "0%")
        crit = attrs.get("crit", "0%")
        launch = attrs.get("launch", "")
        
        # Handle target attribute specially
        target = attrs.get("target", "")
        if not target or target.startswith('.'):  # If target is empty or starts with '.', it's a self-targeting skill
            target = "0"  # Use "0" for self-targeting
        
        # Parse optional attributes
        heal = attrs.get("heal")
        move = attrs.get("move")
        per_battle_limit = int(attrs.get("per_battle_limit", 0)) if "per_battle_limit" in attrs else None
        
        is_crit_valid = attrs.get("is_crit_valid", "False").lower() == "true"
        is_stall_invalidating = attrs.get("is_stall_invalidating", "False").lower() == "true"
        self_target_valid = attrs.get("self_target_valid", "True").lower() == "true"

        level_info = SkillLevelInfo(
            level=level,
            type=type_,
            atk=atk,
            dmg=dmg,
            crit=crit,
            launch=launch,
            target=target,
            is_crit_valid=is_crit_valid,
            effects=effects,
            is_stall_invalidating=is_stall_invalidating,
            self_target_valid=self_target_valid,
            heal=heal,
            move=move,
            per_battle_limit=per_battle_limit
        )

        return skill_id, level_info

    def get_skill_info(self, hero_class: str, skill_id: str, level: int) -> Optional[SkillLevelInfo]:
        """Get skill information for a specific hero class, skill ID, and level"""
        if hero_class not in self.skill_info_cache:
            self._load_hero_skills(hero_class)
        
        skill_info = self.skill_info_cache.get(hero_class, {}).get(skill_id)
        if skill_info:
            return skill_info.get_level_info(level)
        return None

    def _load_hero_skills(self, hero_class: str):
        """Load and parse all skills for a hero class"""
        info_file = os.path.join(
            self.game_install_location,
            "heroes",
            hero_class,
            f"{hero_class}.info.darkest"
        )

        if not os.path.exists(info_file):
            return

        skills = {}
        with open(info_file, 'r') as f:
            for line in f:
                result = self.parse_skill_line(line.strip())
                if result:
                    skill_id, level_info = result
                    if skill_id not in skills:
                        skills[skill_id] = SkillInfo(skill_id)
                    skills[skill_id].add_level(level_info)

        self.skill_info_cache[hero_class] = skills 