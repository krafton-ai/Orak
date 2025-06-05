import os
import re
import ast
import glob
import json
import time
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, List, Optional
from PIL import Image

from dacite import from_dict

from mcp_game_servers.base_env import BaseEnv
from mcp_game_servers.gameio.window_capture import WindowCapture
from mcp_game_servers.utils.types.game_io import Action, Obs

from mcp_game_servers.slay_the_spire.game.communication.coordinator import Coordinator
from mcp_game_servers.slay_the_spire.game.communication.action import StartGameAction
from mcp_game_servers.slay_the_spire.game.rule_agent.agent import SimpleAgent
from mcp_game_servers.slay_the_spire.game.spire.screen import ScreenType
from mcp_game_servers.slay_the_spire.game.spire.game import Game, RoomPhase
from mcp_game_servers.slay_the_spire.game.spire.character import PlayerClass

from mcp_game_servers.slay_the_spire.game.communication.action import Action as Skill
from mcp_game_servers.slay_the_spire.game.communication.action import PlayCardAction, EndTurnAction, ChooseAction, StateAction, CardRewardAction, CancelAction, ProceedAction


logger = logging.getLogger(__name__)

@dataclass
class SlayTheSpireObs(Obs):
    game: Game
    image: Image.Image = None

    def to_text(self):
        is_combat = self.game.play_available
        # is_combat = self.game.play_available or self.game.end_available
        is_card_choice = self.game.choice_available and self.game.screen_type == ScreenType.CARD_REWARD and self.game.room_phase == RoomPhase.COMPLETE

        if is_combat:
            return self.get_combat_prompt()
        
        if is_card_choice:
            return self.get_card_choice_prompt()

        raise NotImplementedError

    def powers2str(self, powers):
        if len(powers) == 0:
            return "- Powers: None\n"

        text = "- Powers:\n"
        for power in powers:
            text += f"  - {power.power_name}: {power.description}\n"
        return text

    def get_combat_prompt(self):
        player_status_text = (
            f"Player:\n"
            f"- Class: {self.game.character.name}\n"
            f"- HP: {self.game.player.current_hp}/{self.game.player.max_hp}\n"
            f"- Block: {self.game.player.block}\n"
            f"- Energy: {self.game.player.energy}\n"
            f"{self.powers2str(self.game.player.powers)}"
            # TODO: add orbs for defect
            # f"- Orbs: {self.game.player.orbs}\n" 
        )

        relics_text = "\n".join(
            [
                f"Relic {index + 1}:\n"
                f"- Name: {relic.name}\n"
                f"- Description: {relic.description}\n"

                for index, relic in enumerate(self.game.relics)
            ]
        )

        cards_in_hand_text = "\n".join(
            [
                f"Card index {index + 1}:\n"
                f"- Name: {card.name}\n"
                f"- Type: {card.type.name.lower()}\n"
                f"- Description: {card.description}\n"
                f"- Cost: {card.cost}\n"
                f"- Has Target: {card.has_target}\n"

                for index, card in enumerate(self.game.hand)
            ]
        )

        monsters_text = "\n".join(
            [
                f"Monster index {index + 1}:\n"
                f"- Name: {monster.name}\n"
                f"- HP: {monster.current_hp}/{monster.max_hp}\n"
                f"- Block: {monster.block}\n"
                f"- Intent: {monster.intent.name.lower()}\n"
                f"- Is gone: {monster.is_gone}\n"
                f"- Is half dead: {monster.half_dead}\n"
                f"- Move base damage: {monster.move_base_damage}\n"
                f"- Move adjust damage: {monster.move_adjusted_damage}\n"
                f"- Move hits: {monster.move_hits}\n"
                f"{self.powers2str(monster.powers)}"

                if not monster.is_gone or monster.half_dead else

                f"Monster index {index + 1}:\n"
                "- Is gone: True\n"

                for index, monster in enumerate(self.game.monsters)
            ]
        )

        prompt = (
            f"COMBAT STATE (Turn {self.game.turn})\n\n"
            f"{player_status_text}\n"
            f"Relics:\n"
            f"{relics_text}\n"
            f"Cards in hand:\n"
            f"{cards_in_hand_text}\n"
            f"Monsters:\n"
            f"{monsters_text}\n"
            f"Valid actions:\n"
            f"- PLAY <card_index>\n"
            f"- PLAY <card_index> <target_index>\n"
            f"- END\n"
        )

        return prompt

    def get_card_choice_prompt(self):
        player_status_text = (
            f"Player:\n"
            f"- Class: {self.game.character.name}\n"
            f"- HP: {self.game.current_hp}/{self.game.max_hp}\n"
        )

        relics_text = "\n".join(
            [
                f"Relic {index + 1}:\n"
                f"- Name: {relic.name}\n"
                f"- Description: {relic.description}\n"

                for index, relic in enumerate(self.game.relics)
            ]
        )

        deck_text = ""
        for index, card in enumerate(self.game.deck):
            deck_text += f"Card index {index + 1}:\n- Name: {card.name}\n- Description: {card.description}\n"

        cards_text = ""
        for index, card in enumerate(self.game.screen.cards):
            cards_text += (
                f"Card index {index + 1}:\n"
                f"- Name: {card.name}\n"
                f"- Type: {card.type.name.lower()}\n"
                f"- Description: {card.description}\n"
                f"- Cost: {card.cost}\n"
            )

        prompt = (
            f"CARD REWARD SELECTION STATE\n\n"
            f"Floor: {self.game.floor}/50\n"
            f"{player_status_text}\n"
            f"Relics:\n"
            f"{relics_text}\n"
            f"Deck:\n"
            f"{deck_text}\n"
            f"Available Card Rewards:\n"
            f"{cards_text}\n"
            f"Valid actions:\n"
            f"- CHOOSE <card_index>\n"
            f"- SKIP\n"
        )

        return prompt

    def evaluate(self):
        if self.game.screen_type == ScreenType.GAME_OVER:
            if self.game.screen.victory:  # beat boss
                return self.game.floor, True
            else:
                return self.game.floor - 1, True
        return self.game.floor - 1, False


@dataclass
class SlayTheSpireAction(Action):
    actions: List[Skill] = field(default_factory=list)

    def __iter__(self) -> Iterator[Skill]:
        return iter(self.actions)

    def __getitem__(self, index: int) -> Skill:
        return self.actions[index]

    def __len__(self) -> int:
        return len(self.actions)


class SlayTheSpireEnv(BaseEnv):
    @dataclass
    class Config:
        task: str
        log_path: str
        input_modality: str

        player_class: str
        ascension_level: int = 0  # hard mode
        seed: int = 0

    cfg: Config

    def configure(self):
        self.player_class = PlayerClass[self.cfg.player_class.upper()]
        self.ascension_level = self.cfg.ascension_level
        self.seed = self.cfg.seed
        self.input_modality = self.cfg.input_modality
        
        self.coordinator = Coordinator()
        self.rule_agent = SimpleAgent(chosen_class=self.player_class)

        self.start_game(self.coordinator, self.rule_agent)

        self.use_image = self.input_modality in ["image", "text_image"]
        if self.use_image:
            self.window_capture = WindowCapture(r"Modded Slay the Spire", mode="bitblt", adjust_dpi=True)

    def start_game(self, coordinator, agent):
        coordinator.signal_ready()
        coordinator.register_state_change_callback(agent.get_next_action_in_game)

        coordinator.clear_actions()
        logger.info("start_game")
        while not coordinator.game_is_ready:
            coordinator.receive_game_state_update(block=True, perform_callbacks=False)
        if not coordinator.in_game:
            logger.info("StartGameAction starts")
            StartGameAction(self.player_class, self.ascension_level, self.seed).execute(coordinator)
            coordinator.receive_game_state_update(block=True)

    def is_awaken_one_half_dead(self, game_state: Game) -> bool:
        if game_state.room_type == "MonsterRoomBoss" and game_state.floor == 50:
            for monster in game_state.monsters:
                if monster.name == "Awakened One" and monster.half_dead:
                    return True
        return False

    def is_handled_by_rules(self, game_state: Game) -> bool:
        logger.info(f"game_state.play_available: {game_state.play_available}")
        logger.info(f"game_state.end_available: {game_state.end_available}")
        logger.info(f"game_state.choice_available: {game_state.choice_available}")
        logger.info(f"game_state.screen_type: {game_state.screen_type}")

        is_combat = game_state.play_available
        is_card_choice = game_state.choice_available and game_state.screen_type == ScreenType.CARD_REWARD and game_state.room_phase == RoomPhase.COMPLETE

        return not is_combat and not is_card_choice

    def initial_obs(self) -> SlayTheSpireObs:
        while True:
            logger.info("Start while loop")
            logger.info(f"action_queue: {self.coordinator.action_queue}")

            if self.coordinator.last_error is not None:
                logger.info(f"Game-side action error occured: {self.coordinator.last_error}")
                logger.info(f"Clear action queue.")
                self.coordinator.clear_actions()
                StateAction().execute(self.coordinator)

            if (len(self.coordinator.action_queue) > 0):
                logger.info(f"self.coordinator.action_queue[0].requires_game_ready: {self.coordinator.action_queue[0].requires_game_ready}")
                logger.info(f"self.coordinator.game_is_ready: {self.coordinator.game_is_ready}")
            if len(self.coordinator.action_queue) > 0 and self.coordinator.action_queue[0].can_be_executed(self.coordinator):
                logger.info("Execute action in action queue")
                try:
                    self.coordinator.execute_next_action()
                except Exception as e:
                    logger.info(f"Agent-side action error occured: {e}")
                    logger.info(f"Clear action queue.")
                    self.coordinator.clear_actions()
                    StateAction().execute(self.coordinator)
                continue

            if len(self.coordinator.action_queue) > 0:
                logger.info("Action queue is not empty, but game is not ready. Wait until state update.")
                # if first action in queue is not executable, wait until game is ready
                self.coordinator.receive_game_state_update(block=True)
                continue

            logger.info("Action queue is empty")
            logger.info("Receive game state update")
            self.coordinator.receive_game_state_update(block=True)

            game_state = self.coordinator.last_game_state
            if self.is_awaken_one_half_dead(game_state):
                # when Awakened One is half dead, the game returns play_available = True,
                # even though the play is not available
                # so we manually end the turn
                self.coordinator.clear_actions()
                self.coordinator.add_action_to_queue(EndTurnAction())
                continue

            if not self.is_handled_by_rules(game_state):
                # if boss room and potion is available, use potion first
                logger.info("Find game state!!")
                logger.info(f"game_state: {game_state.__dict__}")
                self.coordinator.clear_actions()

                if game_state.room_type == "MonsterRoomBoss" and len(game_state.get_real_potions()) > 0:
                # if len(game_state.get_real_potions()) > 0:
                    potion_action = self.rule_agent.use_next_potion()
                    if potion_action is not None:
                        self.coordinator.add_action_to_queue(potion_action)
                        continue

                obs = {"game": game_state}
                if self.use_image:
                    time.sleep(1.0)
                    obs["image"] = self.window_capture.capture(log_path=self.cfg.log_path)

                return from_dict(SlayTheSpireObs, obs)
        
            if game_state.screen_type == ScreenType.GAME_OVER:
                logger.info("Game Over")
                self.coordinator.clear_actions()

                obs = {"game": game_state}
                if self.use_image:
                    time.sleep(1.0)
                    obs["image"] = self.window_capture.capture(log_path=self.cfg.log_path)

                return from_dict(SlayTheSpireObs, obs)

    def obs2text(self, obs: SlayTheSpireObs) -> str:
        return obs.to_text()

    def text2action(self, text: str) -> SlayTheSpireAction:
        actions = []

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("PLAY"):
                pattern = r"^PLAY (\d+)(?: (\d+))?$"
                match = re.match(pattern, line)

                if match:
                    # card_index: 1-index (1-index in prompt)
                    # target_index: 0-index (1-index in prompt)
                    card_index = int(match.group(1))
                    target_index = int(match.group(2)) - 1 if match.group(2) is not None else None

                    # convert index to card object, since the card can be changed in the game
                    if card_index < 1 or card_index > len(self.coordinator.last_game_state.hand):
                        logger.info(f"Invalid card index: {card_index}")
                        return SlayTheSpireAction(actions=[StateAction()])
                    card = self.coordinator.last_game_state.hand[card_index - 1]
                    actions.append(PlayCardAction(card=card, target_index=target_index))
                else:
                    logger.info(f"Invalid command: {line}")
                    return SlayTheSpireAction(actions=[StateAction()])
            elif line.startswith("END"):
                actions.append(EndTurnAction())
            elif line.startswith("CHOOSE"):
                # ensure ChooseAction is called only once
                if len(actions) > 0 and isinstance(actions[0], ChooseAction):
                    # if there is already a ChooseAction in the action queue, skip this action
                    continue

                pattern = r"^CHOOSE (\d+|.+)$"
                match = re.match(pattern, line)

                if match:
                    choice_value = match.group(1).strip()

                    if choice_value.isdigit():
                        # card choose index: 0-index (1-index in prompt)
                        actions.append(ChooseAction(choice_index=int(choice_value) - 1))
                    else:
                        actions.append(ChooseAction(name=choice_value))
                else:
                    logger.info(f"Invalid command: {line}")
                    return SlayTheSpireAction(actions=[StateAction()])
            elif line.startswith("SKIP"):
                if self.coordinator.last_game_state.screen.can_bowl:
                    actions.append(CardRewardAction(bowl=True))
                else:
                    actions.append(ProceedAction())
            else:
                logger.info(f"Invalid command: {line}")
                return SlayTheSpireAction(actions=[StateAction()])
        
        return SlayTheSpireAction(actions=actions)

    def get_game_info(self) -> dict:
        task_description = "Your objective is to reach floor 50 in Slay the Spire."

        return {
            "task_description": task_description,
        }

    def step(
        self, actions: SlayTheSpireAction
    ) -> tuple[SlayTheSpireObs, float, bool, bool, dict[str, Any]]:
        # Add actions to the coordinator action queue
        # Execute get_observation
        # - Within get_observation, execute actions in the coordinator action queue

        self.coordinator.clear_actions()
        self.coordinator.action_queue.extend(actions.actions)
        
        # action will be excuted in initial_obs
        obs = self.initial_obs()

        return obs, 0, False, False, {}

    def evaluate(self, obs: SlayTheSpireObs):
        return obs.evaluate()
