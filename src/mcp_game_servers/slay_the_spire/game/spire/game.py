from enum import Enum

from mcp_game_servers.slay_the_spire.game.spire.relic import Relic
from mcp_game_servers.slay_the_spire.game.spire.card import Card
from mcp_game_servers.slay_the_spire.game.spire.character import PlayerClass, Player, Monster
from mcp_game_servers.slay_the_spire.game.spire.map import Map
from mcp_game_servers.slay_the_spire.game.spire.potion import Potion
from mcp_game_servers.slay_the_spire.game.spire.screen import ScreenType, screen_from_json


class RoomPhase(Enum):
    COMBAT = 1,
    EVENT = 2,
    COMPLETE = 3,
    INCOMPLETE = 4


class Game:

    def __init__(self):

        # General state

        self.current_action = None
        self.current_hp = 0
        self.max_hp = 0
        self.floor = 0
        self.act = 0
        self.gold = 0
        self.seed = 0
        self.character = None
        self.ascension_level = None
        self.relics = []
        self.deck = []
        self.potions = []
        self.map = []

        # Combat state

        self.in_combat = False
        self.player = None
        self.monsters = []
        self.draw_pile = []
        self.discard_pile = []
        self.exhaust_pile = []
        self.hand = []
        self.limbo = []
        self.card_in_play = None
        self.turn = 0
        self.cards_discarded_this_turn = 0

        # Current Screen

        self.screen = None
        self.screen_up = False
        self.screen_type = None
        self.room_phase = None
        self.room_type = None
        self.choice_list = []
        self.choice_available = False

        # Available Commands

        self.end_available = False
        self.potion_available = False
        self.play_available = False
        self.proceed_available = False
        self.cancel_available = False

    @classmethod
    def from_json(cls, json_state, available_commands):
        game = cls()
        game.current_action = json_state.get("current_action", None)
        game.current_hp = json_state.get("current_hp")
        game.max_hp = json_state.get("max_hp")
        game.floor = json_state.get("floor")
        game.act = json_state.get("act")
        game.gold = json_state.get("gold")
        game.seed = json_state.get("seed")
        game.character = PlayerClass[json_state.get("class")]
        game.ascension_level = json_state.get("ascension_level")
        game.relics = [Relic.from_json(json_relic) for json_relic in json_state.get("relics")]
        game.deck = [Card.from_json(json_card) for json_card in json_state.get("deck")]
        game.map = Map.from_json(json_state.get("map"))
        game.potions = [Potion.from_json(potion) for potion in json_state.get("potions")]
        game.act_boss = json_state.get("act_boss", None)

        # Screen State

        game.screen_up = json_state.get("is_screen_up", False)
        game.screen_type = ScreenType[json_state.get("screen_type")]
        game.screen = screen_from_json(game.screen_type, json_state.get("screen_state"))
        game.room_phase = RoomPhase[json_state.get("room_phase")]
        game.room_type = json_state.get("room_type")
        game.choice_available = "choice_list" in json_state
        if game.choice_available:
            game.choice_list = json_state.get("choice_list")

        # Combat state

        game.in_combat = game.room_phase == RoomPhase.COMBAT
        if game.in_combat:
            combat_state = json_state.get("combat_state")
            game.player = Player.from_json(combat_state.get("player"))
            game.monsters = [Monster.from_json(json_monster) for json_monster in combat_state.get("monsters")]
            for i, monster in enumerate(game.monsters):
                monster.monster_index = i
            game.draw_pile = [Card.from_json(json_card) for json_card in combat_state.get("draw_pile")]
            game.discard_pile = [Card.from_json(json_card) for json_card in combat_state.get("discard_pile")]
            game.exhaust_pile = [Card.from_json(json_card) for json_card in combat_state.get("exhaust_pile")]
            game.hand = [Card.from_json(json_card) for json_card in combat_state.get("hand")]
            game.limbo = [Card.from_json(json_card) for json_card in combat_state.get("limbo", [])]
            game.card_in_play = combat_state.get("card_in_play", None)
            if game.card_in_play is not None:
                game.card_in_play = Card.from_json(game.card_in_play)
            game.turn = combat_state.get("turn", 0)
            game.cards_discarded_this_turn = combat_state.get("cards_discarded_this_turn", 0)

        # Available Commands

        game.end_available = "end" in available_commands
        game.potion_available = "potion" in available_commands
        game.play_available = "play" in available_commands
        game.proceed_available = "proceed" in available_commands or "confirm" in available_commands
        game.cancel_available = "cancel" in available_commands or "leave" in available_commands \
                                or "return" in available_commands or "skip" in available_commands

        return game

    def are_potions_full(self):
        for potion in self.potions:
            if potion.potion_id == "Potion Slot":
                return False
        return True

    def get_real_potions(self):
        potions = []
        for potion in self.potions:
            if potion.potion_id != "Potion Slot":
                potions.append(potion)
        return potions
