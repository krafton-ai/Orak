import os
import json
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional

from dacite import from_dict

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.utils.types.game_io import Action, Obs

from .utils.SaveFileReader import SaveFileReader
from .utils.Battle import battle
from .utils.NavigateDungeon import navigate_dungeon, get_party_tile, get_dungeon_path, MissionComplete
from .utils.DungeonInteractions import loot_treasure
from .utils.Roster import Party
from .utils.Controls import Controller, attack_target, heal_target, swap_hero
from .utils.Items import Inventory
from .utils.AttackSkills import AttackSkills
from .utils.SkillInfo import SkillInfoParser

RoundNumber = 1
GLOBAL_SCORE = 0  # Add global score variable


def safe_load_json(file_path, max_retries=5, delay=0.5):
    for i in range(max_retries):
        try:
            # Open file in binary mode
            with open(file_path, "rb") as f:
                content = f.read()
                # Try different encodings
                try:
                    # Try UTF-8 first
                    decoded = content.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        # Try Latin-1 as fallback
                        decoded = content.decode('latin-1')
                    except UnicodeDecodeError:
                        # Try with errors ignored as last resort
                        decoded = content.decode('utf-8', errors='ignore')
                
                return json.loads(decoded)
        except (json.JSONDecodeError, IOError):
            time.sleep(delay)

    raise RuntimeError(f"Failed to load JSON file: {file_path}")


STATE_TEMPLATE = (
    "CURRENTLY ACTING HERO:\n"
    "{hero}\n\n"
    "PARTY:\n"
    "{party}\n\n"
    "ENEMY FORMATION:\n"
    "{enemy_formation}"
)


@dataclass
class DarkestDungeonObs(Obs):
    # info: Info
    raid_info: Any #RaidInfo
    inventory: Any #Inven
    party_info: Any #PartyInfo
    map_info: Optional[Any] #Optional[MapInfo]
    party: Any
    hero: Any
    enemy_formation: Any
    in_town: bool
    mission_complete: bool = False
    image: Any = None  # Add image field

    def format_hero(self, skill_info_parser: SkillInfoParser) -> str:
        if self.hero is None:
            return "No active hero (in town)"
        h = self.hero

        # Optional skill usage counters for specific hero classes
        additional_skills_info = []
        if h.heroClass == 'plague_doctor':
            additional_skills_info.append(f"Emboldening Vapours used: {getattr(h, 'emboldening_vapours_count', 0)}")
            additional_skills_info.append(f"Blinding Gas used: {getattr(h, 'blinding_gas_count', 0)}")
        elif h.heroClass == 'hellion':
            additional_skills_info.append(f"Barbaric Yawp used: {getattr(h, 'barbaric_yawp_count', 0)}")
        elif h.heroClass == 'man_at_arms':
            additional_skills_info.append(f"Bolster used: {getattr(h, 'bolster_count', 0)}")

        # Combine "additional skills" info into a single string
        skills_info_str = "\n    ".join(additional_skills_info)

        # Convert quirks/diseases/trinkets/buffs to strings safely
        quirks_str = (
            ", ".join([f"{q['name']} (rating={q['rating']})" for q in h.quirks])
            if h.quirks
            else "None"
        )
        diseases_str = (
            ", ".join([f"{d['name']} (rating={d['rating']})" for d in h.diseases])
            if h.diseases
            else "None"
        )
        trinkets_str = ", ".join(h.trinkets) if h.trinkets else "None"

        buffs_str = ", ".join(str(b) for b in h.buffs) if h.buffs else "None"

        hero_str = (
            f"Name: {h.name}\n"
            f"Class: {h.heroClass}\n"
            f"Rank (position): {h.rank}\n"
            f"HP: {h.currentHp}/{h.maxHp}\n"
            f"Stress: {h.stress}\n"
            f"Stunned: {h.stunned}\n"
            f"Already Moved: {h.already_moved}\n"
            f"Bleed: {h.bleedAmount} (duration: {h.bleedDuration})\n"
            f"Blight: {h.blightAmount} (duration: {h.blightDuration})\n"
            f"Weapon Rank: {h.weaponRank}\n"
            f"Armor Rank: {h.armorRank}\n"
            f"Resolve Level: {h.resolveLevel}\n"
            f"Buffs: {buffs_str}\n"
            f"Quirks: {quirks_str}\n"
            f"Diseases: {diseases_str}\n"
            f"Trinkets: {trinkets_str}\n"
            f"Camping Skills: {', '.join(h.campingSkills) if h.campingSkills else 'None'}\n"
            f"Healer: {h.healer}\n"
            f"Stress Healer: {h.stressHealer}\n"
            f"Trap Disarm: {h.traps_skill}\n"
            f"Speed: {h.speed}\n"
        )
        
        # Get available skills based on rank constraints
        enumerated_skills = []
        for i, (skill_name, skill_level) in enumerate(h.skills.items(), start=1):
            # Get detailed skill info from .info.darkest file
            skill_info = skill_info_parser.get_skill_info(h.heroClass, skill_name.lower().replace(" ", "_"), skill_level)
            
            if skill_info:
                # Get rank constraints from skill info
                launch_ranks = skill_info.get_launch_ranks()
                target_ranks = skill_info.get_target_ranks()
                
                # Get enemy positions - handle enemies that occupy multiple ranks
                enemy_positions = set()
                for enemy in self.enemy_formation:
                    if isinstance(enemy.rank, list):
                        enemy_positions.update(enemy.rank)  # Add all ranks occupied by this enemy
                    else:
                        enemy_positions.add(enemy.rank)  # Single rank
                
                # Format target information
                if 0 in target_ranks:  # Special case for party-wide skills
                    target_info = "(targets: party-wide)"
                else:
                    # Check if the skill targets allies
                    if skill_info.is_ally_targeting():
                        if skill_info.target.startswith('@~'):
                            target_info = f"(targets: ALL allies in ranks {sorted(target_ranks)})"
                        else:
                            target_info = f"(can target one ally from ranks: {sorted(target_ranks)})"
                    else:
                        # Check if the skill can target all enemies in ALL ranks (starts with ~)
                        if skill_info.target.startswith('~'):
                            target_info = f"(targets: ALL enemies in ranks {sorted(target_ranks)})"
                        else:
                            target_info = f"(can target one enemy from ranks: {sorted(target_ranks)})"
                
                # Add detailed skill info
                skill_details = []
                skill_details.append(f"Level: {skill_level}")
                skill_details.append(f"Type: {skill_info.type}")
                
                # Indicate if this is a healing skill
                if skill_info.is_healing_skill():
                    skill_details.append("Type: Healing")
                
                skill_details.append(f"Accuracy: {skill_info.atk}")
                skill_details.append(f"Damage: {skill_info.dmg}")
                
                # Only show crit if the skill can crit
                if skill_info.is_crit_valid:
                    skill_details.append(f"Crit: {skill_info.crit}")
                
                # Add healing info if available
                heal_range = skill_info.get_heal_range()
                if heal_range:
                    min_heal, max_heal = heal_range
                    skill_details.append(f"Heal: {min_heal}-{max_heal}")
                
                # Add movement info if available
                move_info = ""
                backward, forward = skill_info.get_move_info()
                if backward > 0 or forward > 0:
                    move_info = f" [Move: {'backward ' + str(backward) if backward > 0 else ''}{'forward ' + str(forward) if forward > 0 else ''}]"
                
                # Add per battle limit if available
                if skill_info.per_battle_limit:
                    skill_details.append(f"Uses per battle: {skill_info.per_battle_limit}")
                
                if skill_info.effects:
                    skill_details.append(f"Effects: {', '.join(skill_info.effects)}")
                
                # Add stun/blight info if available
                effect_info = ""
                if skill_info.effects:
                    for effect in skill_info.effects:
                        if effect.startswith("stun"):
                            effect_info = f" [Stun chance: {effect.split('_')[1]}%]"
                        elif effect.startswith("blight"):
                            effect_info = f" [DoT damage: {effect.split('_')[1]}]"
                
                # Check if skill is available from current rank and has valid targets
                is_available_from_rank = h.rank in launch_ranks
                has_valid_targets = 0 in target_ranks or bool(target_ranks & enemy_positions)  # Party-wide or has enemies in target ranks
                is_available = is_available_from_rank and has_valid_targets
                
                # Create availability message
                if not is_available_from_rank:
                    availability = f"[UNAVAILABLE from rank {h.rank}]"
                elif not has_valid_targets:
                    availability = "[UNAVAILABLE - no valid targets]"
                else:
                    availability = "[AVAILABLE]"
                
                skill_str = f"{i}. {skill_name} {target_info} (can use from ranks: {sorted(launch_ranks)}){effect_info}{move_info} {availability}"
                if skill_details:
                    skill_str += "\n    " + "\n    ".join(skill_details)
                
                enumerated_skills.append(skill_str)
            else:
                # Skill not found in .info.darkest file
                enumerated_skills.append(f"{i}. {skill_name} (skill info not found)")

        skills_block = "\n".join(enumerated_skills)
        hero_str += f"\n\nSkills (Slot-Based):\n{skills_block}"

        # Add any special skill usage lines
        if skills_info_str.strip():
            hero_str += f"\nAdditional Class Skills:\n    {skills_info_str}"

        return hero_str.strip()

    def format_party(self) -> str:
        """
        Format the entire party's info as a multi-line string.
        This includes each hero's name, class, position, HP, stress, and any other relevant data.
        """
        lines = []
        for idx, member in enumerate(self.party, start=1):
            # Basic line for each hero in party
            line = (
                f"{idx}. {member.name} ({member.heroClass}) | "
                f"Rank: {member.rank} | "
                f"HP: {member.currentHp}/{member.maxHp} | "
                f"Stress: {member.stress}"
                f"{' | STUNNED' if member.stunned else ''}"
                f"{' | ALREADY MOVED' if member.already_moved else ''}"
            )
            lines.append(line)
        return "\n".join(lines)
    
    def format_enemy_formation(self) -> str:
        """
        Format each enemy in the formation, displaying key info such as name, HP, rank, and special statuses.
        """
        lines = []
        for idx, enemy in enumerate(self.enemy_formation, start=1):
            line = (
                f"{idx}. {enemy.name} "
                f"(BattleId: {enemy.battleId}, Rank: {enemy.rank})\n"
                f"   HP: {enemy.currentHp}/{enemy.maxHp}, "
                f"Stunned: {enemy.stunned}, "
                f"Already Moved: {enemy.alreadyMoved}\n"
                f"   Bleed: {enemy.bleedAmount} (dur: {enemy.bleedDuration}), "
                f"Blight: {enemy.blightAmount} (dur: {enemy.blightDuration})\n"
                f"   Stun Resist: {enemy.stunResist}\n"
                f"   Threat Level: {enemy.threat}\n"
                f"   Tags: "
                f"{'Tank ' if enemy.isTank else ''}"
                f"{'CanBeKilledIn1Hit ' if enemy.canBeKilledIn1Hit else ''}"
                f"{'LowHP ' if enemy.lowHp else ''}"
                f"{'AlreadyDying ' if enemy.alreadyGoingToDie else ''}"
            )
            lines.append(line.strip())
        return "\n\n".join(lines)

    def to_text(self, skill_info_parser=None):
        # If skill_info_parser is not provided, try to get it from self or as a private attribute
        if skill_info_parser is None:
            if hasattr(self, 'skill_info_parser') and self.skill_info_parser is not None:
                skill_info_parser = self.skill_info_parser
            elif hasattr(self, '_skill_info_parser') and self._skill_info_parser is not None:
                skill_info_parser = self._skill_info_parser
            else:
                raise ValueError("skill_info_parser must be provided for DarkestDungeonObs.to_text")
        return STATE_TEMPLATE.format(
            hero=self.format_hero(skill_info_parser),
            party=self.format_party(),
            enemy_formation=self.format_enemy_formation()
        )
    
    TASK_MAX_COMBATS = {
        "first_embark_after_tutorial": 4,
        "second_embark_after_tutorial": 2
    }

    def evaluate(self, task_name, save_editor_path):
        """
        Scoring rules:

            – While combats remain:
                    score = 0.4 * (combats_cleared / MAX_COMBATS[task])

            – After all combats are cleared:
                    score = 0.4                                   # full exploration term
                          + 0.3 * (heroes_survived / 4)
                          + 0.3 * (1 – total_stress / 800)

              Dead heroes contribute max stress (200) to the stress term.
        """
        global GLOBAL_SCORE

        if task_name not in {"first_embark_after_tutorial",
                             "second_embark_after_tutorial"}:
            raise NotImplementedError

        # 1.  Combats cleared so far
        try:
            data = safe_load_json(f"{save_editor_path}/game_states/persist.raid.json")
            # If safe_load_json returned None for some reason
            if data is None:
                raise ValueError("persist.raid.json returned None")
            # drill into the correct keys
            combats_cleared = data["base_root"] \
                                ["raid_instance"] \
                                ["town_progression_goals"] \
                                ["town_progression_battle"] \
                                ["current_battle_count"]
        except Exception:
            # JSON load/index failed — bail out with old score
            done = self.in_town or getattr(self, "mission_complete", False)
            return GLOBAL_SCORE, done
        
        max_combats = self.TASK_MAX_COMBATS.get(task_name, 1)

        # 2.  Survival & stress
        TOTAL_HEROES          = 4            # tutorial party size is fixed
        survived_heroes       = len(self.party)
        survival_ratio        = survived_heroes / TOTAL_HEROES

        MAX_STRESS_PER_HERO   = 200
        max_possible_stress   = MAX_STRESS_PER_HERO * TOTAL_HEROES

        live_stress           = sum(hero.stress for hero in self.party)
        dead_heroes           = TOTAL_HEROES - survived_heroes
        total_stress          = live_stress + dead_heroes * MAX_STRESS_PER_HERO
        stress_ratio          = (max_possible_stress - total_stress) / max_possible_stress

        # 3.  Final score
        if combats_cleared < max_combats:
            calculated_score = 0.4 * (combats_cleared / max_combats)
        else:
            calculated_score = 0.4 + 0.3 * survival_ratio + 0.3 * stress_ratio

        GLOBAL_SCORE = calculated_score   # always keep the newest value

        done = self.in_town or getattr(self, "mission_complete", False)
        return GLOBAL_SCORE, done

    def obs2text(self):
        return self.to_text()


@dataclass
class DarkestDungeonAction(Action):
    """
    A simplified action representation where the LLM just picks:
      - action_type: "idle", "attack", "heal", "swap"
      - skill_slot: which hero skill slot (1..N) – only relevant if "attack" or "heal"
      - target_index: which enemy or ally index (1..N)
      - swap_distance: integer for "swap" (positive=forward, negative=backward, 0=skip)
      - current_rank: hero's current rank (1..4), used only for "swap"
    """
    VALID_ACTION_TYPES = ["idle", "attack", "heal", "swap"]

    action_type: str = "idle"
    skill_slot: Optional[int] = None
    target_index: Optional[int] = None
    swap_distance: int = 0
    current_rank: Optional[int] = None  # used if action_type == "swap"

    @classmethod
    def from_string(cls, action_str: str) -> "DarkestDungeonAction":
        """
        Parse a text command from the LLM into a DarkestDungeonAction.

        Example commands:
          - "attack target 3 using skill slot 2"
          - "heal target 2 using skill slot 1"
          - "swap rank 3 hero forward by 1"
          - "swap rank 2 hero backward by 1"
          - "swap rank 4 hero skip"
        """
        import re
        s = action_str.lower().strip()
        # Patterns for new natural language commands
        attack_pat = re.compile(r"attack target (\d+) using skill slot (\d+)")
        heal_pat = re.compile(r"heal target (\d+) using skill slot (\d+)")
        swap_pat = re.compile(r"swap rank (\d+) hero (forward|backward) by (\d+)")
        swap_skip_pat = re.compile(r"swap rank (\d+) hero skip")
        idle_pat = re.compile(r"^(idle|skip|pass)$")

        # Try new patterns first
        m = attack_pat.match(s)
        if m:
            return cls(action_type="attack", target_index=int(m.group(1)), skill_slot=int(m.group(2)))
        m = heal_pat.match(s)
        if m:
            return cls(action_type="heal", target_index=int(m.group(1)), skill_slot=int(m.group(2)))
        m = swap_pat.match(s)
        if m:
            current_rank = int(m.group(1))
            direction = m.group(2)
            dist = int(m.group(3))
            swap_distance = dist if direction == "forward" else -dist
            return cls(action_type="swap", current_rank=current_rank, swap_distance=swap_distance)
        m = swap_skip_pat.match(s)
        if m:
            current_rank = int(m.group(1))
            return cls(action_type="swap", current_rank=current_rank, swap_distance=0)
        m = idle_pat.match(s)
        if m:
            return cls(action_type="idle")

        # Fallback: legacy parsing (original logic)
        parts = s.split()
        if not parts:
            return cls(action_type="idle")

        action_type = "idle"
        skill_slot = None
        target_index = None
        swap_distance = 0
        current_rank = None

        i = 0
        while i < len(parts):
            token = parts[i]

            # Attack or Heal
            if token in ("attack", "heal"):
                action_type = token

            elif token == "slot":
                # Next token should be an integer (1..N), and must be <= 4
                if i + 1 < len(parts):
                    try:
                        skill_slot_candidate = int(parts[i + 1])
                        if skill_slot_candidate > 4:
                            raise ValueError("skill_slot must be 4 or less")
                        skill_slot = skill_slot_candidate
                        i += 1
                    except ValueError:
                        pass

            elif token == "target":
                # Next token should be an integer (1..N), and must be <= 4
                if i + 1 < len(parts):
                    try:
                        target_index_candidate = int(parts[i + 1])
                        if target_index_candidate > 4:
                            raise ValueError("target_index must be 4 or less")
                        target_index = target_index_candidate
                        i += 1
                    except ValueError:
                        pass

            elif token == "swap":
                action_type = "swap"
                # The next tokens might be "rank X", "forward Y", "backward Z", "skip", etc.
                # We'll keep reading until we run out of tokens or see an unrelated command.
            elif token == "rank":
                # For swap, we want to capture the hero's current rank
                if i + 1 < len(parts):
                    try:
                        current_rank = int(parts[i + 1])
                        i += 1
                    except ValueError:
                        pass

            elif token in ("forward", "backward", "skip"):
                # Only relevant if action_type is "swap"
                if action_type == "swap":
                    if token == "skip":
                        swap_distance = 0
                    elif token == "forward":
                        # e.g. "forward 2"
                        if i + 1 < len(parts):
                            try:
                                dist = int(parts[i + 1])
                                swap_distance = +dist
                                i += 1
                            except ValueError:
                                swap_distance = 1
                    elif token == "backward":
                        # e.g. "backward 2" => -2
                        if i + 1 < len(parts):
                            try:
                                dist = int(parts[i + 1])
                                swap_distance = -abs(dist)
                                i += 1
                            except ValueError:
                                swap_distance = -1

            elif token in ("idle", "skip", "pass"):
                # Might see "idle" anywhere
                action_type = "idle"

            i += 1

        return cls(
            action_type=action_type,
            skill_slot=skill_slot,
            target_index=target_index,
            swap_distance=swap_distance,
            current_rank=current_rank,
        )

    def to_str(self) -> str:
        """
        Convert this action into a text command (for logging or debugging).
        """
        if self.action_type == "idle":
            return "idle"

        elif self.action_type in ("attack", "heal"):
            parts = [self.action_type]
            if self.skill_slot is not None:
                parts.append(f"slot {self.skill_slot}")
            if self.target_index is not None:
                parts.append(f"target {self.target_index}")
            return " ".join(parts)

        elif self.action_type == "swap":
            # e.g. "swap rank 3 forward 1"
            # or "swap rank 2 backward 2"
            # or "swap rank 4 skip"
            base = f"swap"
            if self.current_rank is not None:
                base += f" rank {self.current_rank}"

            if self.swap_distance == 0:
                return f"{base} skip"
            elif self.swap_distance > 0:
                return f"{base} forward {self.swap_distance}"
            else:
                return f"{base} backward {abs(self.swap_distance)}"

        return "idle"


class DarkestDungeonEnv(BaseEnv):
    @dataclass
    class Config:
        save_editor_path: str
        game_install_location: str
        steam_user_id: str
        profile_number: str
        log_path: str
        task: str
        input_modality: str = "text"

    cfg: Config
    skill_info_parser: SkillInfoParser
    current_hero: Any = None  # Add current_hero as an attribute
    enemy_formation: Any = None  # Add enemy_formation as an attribute
    party: Any = None  # Add party as an attribute
    input_modality: str
    use_image: bool
    window_capture: Any = None  # Add window_capture as an attribute

    def configure(self):
        self.save_editor_path = self.cfg.save_editor_path
        # profile_path = f'~/Library/Application Support/Steam/userdata/{self.cfg.steam_user_id}/262060/remote'
        profile_path = f'C:/Program Files (x86)/Steam/userdata/{self.cfg.steam_user_id}/262060/remote'
        save_profile_path = Path(os.path.expanduser(f'{profile_path}/profile_{self.cfg.profile_number}'))
        self.sfr = SaveFileReader(self.save_editor_path, save_profile_path, self.cfg.game_install_location)
        self.c = Controller(debug=False)
        self.skill_info_parser = SkillInfoParser(self.cfg.game_install_location)
        self.task_name = self.cfg.task
        self.current_hero = None  # Initialize current_hero
        self.enemy_formation = None  # Initialize enemy_formation
        self.party = None  # Initialize party
        # Add input_modality and image capture setup
        self.input_modality = getattr(self.cfg, 'input_modality', 'text')
        self.use_image = self.input_modality in ["text_image"]
        if self.use_image:
            from mcp_game_servers.gameio.window_capture import WindowCapture
            # Darkest Dungeon 창 이름 패턴은 필요에 따라 조정
            self.window_capture = WindowCapture(r"Darkest Dungeon", mode="bitblt")

    def initial_obs(self) -> DarkestDungeonObs:
        global RoundNumber
        state_json = {}
        
        while True:

            self.sfr.decrypt_save_info('persist.game.json')
            info = safe_load_json(f'{self.save_editor_path}/game_states/persist.game.json')['base_root']

            state_json['in_town'] = False

            if info['inraid']:
                self.sfr.decrypt_save_info('persist.raid.json')
                self.sfr.decrypt_save_info('persist.map.json')

            raid_info = safe_load_json(f'{self.save_editor_path}/game_states/persist.raid.json')['base_root']
            inventory = Inventory(raid_info)
            state_json['raid_info'] = raid_info
            state_json['inventory'] = inventory

            self.sfr.decrypt_save_info('persist.roster.json')
            roster_info = safe_load_json(f'{self.save_editor_path}/game_states/persist.roster.json')['base_root']
            party_order = raid_info['party']['heroes']
            party_info = Party(roster_info, party_order)
            state_json['party_info'] = party_info

            map_info = safe_load_json(f'{self.save_editor_path}/game_states/persist.map.json')['base_root']
            state_json['map_info'] = map_info

            if not info['inraid']:
                state_json['in_town'] = True
                state_json['party'] = []
                state_json['hero'] = None
                state_json['enemy_formation'] = []
                state_json['mission_complete'] = False
                # Add image if use_image is enabled
                if hasattr(self, 'use_image') and self.use_image:
                    state_json['image'] = self.window_capture.capture(log_path=self.cfg.log_path)
                obs = from_dict(DarkestDungeonObs, state_json)
                # Always attach skill_info_parser to obs for later use
                obs.skill_info_parser = self.skill_info_parser
                return obs
            
            state_json['in_town'] = False

            if raid_info['inbattle']:
                party, hero, raid_info, enemy_formation = battle(inventory, None, self.sfr, False)
                state_json['party'] = party
                state_json['hero'] = hero
                state_json['raid_info'] = raid_info
                state_json['enemy_formation'] = enemy_formation
                
                # Update current_hero, enemy_formation, and party attributes
                self.current_hero = hero
                self.enemy_formation = enemy_formation
                self.party = party
                # Add image if use_image is enabled
                if hasattr(self, 'use_image') and self.use_image:
                    state_json['image'] = self.window_capture.capture(log_path=self.cfg.log_path)
                obs = from_dict(DarkestDungeonObs, state_json)
                # Always attach skill_info_parser to obs for later use
                obs.skill_info_parser = self.skill_info_parser
                return obs
            else:
                areas = map_info['map']['static_dynamic']['areas']
                static_areas = map_info['map']['static_dynamic']['static_save']['base_root']['areas']
                location_number = raid_info['in_area']
                location = next(index for index, area in areas.items() if static_areas[index]['id'] == location_number)

                queued_loot = raid_info['loot']['queue_items']['items']
                battle_reward = raid_info['loot']['result']['inventory_system']['items'] \
                    if 'result' in raid_info['loot'] else []
                if len(queued_loot) > 0 or len(battle_reward) > 0:
                    if location.startswith('co'):
                        static_tiles = static_areas[location]['tiles']
                        hallway_length = len(static_tiles) - 1
                        last_room_number = raid_info['last_room_id']  # 1111584611
                        reverse = last_room_number != static_tiles['tile0']['door_to']['area_to']
                        party_tile = get_party_tile(raid_info, hallway_length, reverse)
                    else:
                        party_tile = 0
                    dungeon_path, _ = get_dungeon_path(raid_info, static_areas, location)
                    loot_treasure(raid_info, inventory, areas, location, party_info.heroes,
                                    tile_number=party_tile, dungeon_path=dungeon_path, sfr=self.sfr, debug=False)
                    self.sfr.decrypt_save_info('persist.raid.json')
                    raid_info = safe_load_json(f'{self.save_editor_path}/game_states/persist.raid.json')['base_root']
                    inventory = Inventory(raid_info)
            
                time.sleep(.5)  # give enough time for loot/curio screen to close and mission complete to open
                self.c.write(self.c.b, 4)  # close out of menu (e.g. mission complete)
                time.sleep(.2)  # give enough time for mission complete screen to close

                navigate_dungeon(raid_info, areas, static_areas, inventory, party_info, location, self.sfr, debug=False)

    def obs2text(self, obs: DarkestDungeonObs) -> str:
        return obs.to_text()
    
    def text2action(self, text: str) -> "DarkestDungeonAction":
        return DarkestDungeonAction.from_string(text)
    
    def get_game_info(self) -> dict:
        return {
            "prev_state_str": None,
            "task_description": "Complete your first expedition after the tutorial. Explore all rooms in the dungeon while keeping your heroes alive and managing their stress levels."
        }
    
    def is_invalid_action(self, action: "DarkestDungeonAction") -> bool:
        # Idle은 항상 허용
        if action.action_type == "idle":
            return False
        # attack, heal: skill_slot, target_index가 None이거나 1~4 범위 밖이면 무효
        if action.action_type in ("attack", "heal"):
            if action.skill_slot is None or action.target_index is None:
                return True
            if not (1 <= action.skill_slot <= 4):
                return True
            if not (1 <= action.target_index <= 4):
                return True
        # swap: current_rank이 None이거나 1~4 범위 밖이면 무효
        if action.action_type == "swap":
            if action.current_rank is None:
                return True
            if not (1 <= action.current_rank <= 4):
                return True
        # 그 외는 무효
        if action.action_type not in DarkestDungeonAction.VALID_ACTION_TYPES:
            return True
        return False

    def step(
        self, action: "DarkestDungeonAction"
    ) -> tuple["DarkestDungeonObs", float, bool, bool, dict[str, Any]]:
        if self.is_invalid_action(action):
            print(f"Invalid action received: {action}")
            obs = self.initial_obs()
            done = obs.in_town
            return obs, 0, done, False, {"invalid_action": True}
        if action.action_type == "attack":
            # We expect action.skill_slot (1-based) and action.target_index (1-based)
            if action.skill_slot is None or action.target_index is None:
                print("Invalid attack parameters; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            if not self.current_hero:
                print("No current hero found; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            # Get the current hero's skill info
            skill_name = list(self.current_hero.skills.keys())[action.skill_slot - 1]  # Convert 1-based to 0-based
            skill_level = self.current_hero.skills[skill_name]
            skill_info = self.skill_info_parser.get_skill_info(self.current_hero.heroClass, skill_name.lower().replace(" ", "_"), skill_level)
            
            if not skill_info:
                print(f"Skill info not found for {skill_name}; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            # Check if skill can be used from current rank
            launch_ranks = skill_info.get_launch_ranks()
            if self.current_hero.rank not in launch_ranks:
                print(f"Skill {skill_name} cannot be used from rank {self.current_hero.rank}; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            # Get enemy positions from environment attribute, handling both single ranks and multiple ranks
            enemy_positions = set()
            for enemy in self.enemy_formation:
                if isinstance(enemy.rank, list):
                    enemy_positions.update(enemy.rank)  # Add all ranks occupied by this enemy
                else:
                    enemy_positions.add(enemy.rank)  # Single rank

            # Check if there are valid targets based on skill targeting rules
            target_ranks = skill_info.get_target_ranks()
            
            # Special case for self-targeting skills
            if 0 in target_ranks:
                has_valid_targets = True
            else:
                # For enemy-targeting skills
                if not skill_info.is_ally_targeting():
                    has_valid_targets = bool(target_ranks & enemy_positions)
                else:
                    # For ally-targeting skills
                    ally_positions = {hero.rank for hero in self.party}
                    if skill_info.target.startswith('@~'):
                        # Must have allies in ALL target ranks
                        has_valid_targets = all(rank in ally_positions for rank in target_ranks)
                    else:
                        # Must have at least one ally in any target rank
                        has_valid_targets = bool(target_ranks & ally_positions)
            
            if not has_valid_targets:
                print(f"No valid targets for skill {skill_name}; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            # Convert target_index from 1-based to 0-based for the function
            target_idx_0_based = action.target_index - 1
            print(f"Executing ATTACK: skill slot={action.skill_slot}, target={action.target_index}")
            attack_target(
                target_index=target_idx_0_based,
                skill_slot=action.skill_slot
            )
        
        elif action.action_type == "heal":
            # We expect action.skill_slot (1-based) and action.target_index (1-based)
            if action.skill_slot is None or action.target_index is None:
                print("Invalid heal parameters; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            if not self.current_hero:
                print("No current hero found; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            # Get the current hero's skill info
            skill_name = list(self.current_hero.skills.keys())[action.skill_slot - 1]  # Convert 1-based to 0-based
            skill_level = self.current_hero.skills[skill_name]
            skill_info = self.skill_info_parser.get_skill_info(self.current_hero.heroClass, skill_name.lower().replace(" ", "_"), skill_level)
            
            if not skill_info:
                print(f"Skill info not found for {skill_name}; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            # Check if skill can be used from current rank
            launch_ranks = skill_info.get_launch_ranks()
            if self.current_hero.rank not in launch_ranks:
                print(f"Skill {skill_name} cannot be used from rank {self.current_hero.rank}; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            # Check if target is valid for healing
            target_ranks = skill_info.get_target_ranks()
            ally_positions = {hero.rank for hero in self.party}
            
            # For healing skills, we need to check ally positions
            if skill_info.target.startswith('@~'):
                # Must have allies in ALL target ranks
                has_valid_targets = all(rank in ally_positions for rank in target_ranks)
            else:
                # Must have at least one ally in any target rank
                has_valid_targets = bool(target_ranks & ally_positions)
            
            if not has_valid_targets:
                print(f"Invalid target rank {action.target_index} for healing skill {skill_name}; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            print(f"Executing HEAL: skill slot={action.skill_slot}, target rank={action.target_index}")
            heal_target(
                target_rank=action.target_index,  # "heal_target" expects 1-based rank
                skill_slot=action.skill_slot
            )
        elif action.action_type == "swap":
            # We expect action.current_rank (1-based) and action.swap_distance
            if action.current_rank is None:
                print("No current_rank specified for swap; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

            # Validate swap parameters
            if not (1 <= action.current_rank <= 4):
                print(f"Invalid current rank {action.current_rank}; doing nothing.")
                return self.initial_obs(), 0, False, False, {}

#            new_rank = action.current_rank + action.swap_distance
#            if not (1 <= new_rank <= 4):
#                print(f"Invalid new rank {new_rank}; doing nothing.")
#                return self.initial_obs(), 0, False, False, {}

            print(f"Executing SWAP: current_rank={action.current_rank}, distance={action.swap_distance}")
            swap_hero(
                current_rank=action.current_rank,
                swap_distance=action.swap_distance,
            )

        time.sleep(10.0)
        obs = self.initial_obs()
        done = obs.in_town
        return obs, 0, done, False, {}
    
    def evaluate(self, obs: DarkestDungeonObs):
        return obs.evaluate(self.task_name, self.save_editor_path)
