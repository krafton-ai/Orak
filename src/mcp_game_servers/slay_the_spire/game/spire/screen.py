from enum import Enum

from mcp_game_servers.slay_the_spire.game.spire.potion import Potion
from mcp_game_servers.slay_the_spire.game.spire.card import Card
from mcp_game_servers.slay_the_spire.game.spire.relic import Relic
from mcp_game_servers.slay_the_spire.game.spire.map import Node


class ScreenType(Enum):
    EVENT = 1
    CHEST = 2
    SHOP_ROOM = 3
    REST = 4
    CARD_REWARD = 5
    COMBAT_REWARD = 6
    MAP = 7
    BOSS_REWARD = 8
    SHOP_SCREEN = 9
    GRID = 10
    HAND_SELECT = 11
    GAME_OVER = 12
    COMPLETE = 13
    NONE = 14


class ChestType(Enum):
    SMALL = 1
    MEDIUM = 2
    LARGE = 3
    BOSS = 4
    UNKNOWN = 5


class RewardType(Enum):
    CARD = 1
    GOLD = 2
    RELIC = 3
    POTION = 4
    STOLEN_GOLD = 5
    EMERALD_KEY = 6
    SAPPHIRE_KEY = 7


class RestOption(Enum):
    DIG = 1
    LIFT = 2
    RECALL = 3
    REST = 4
    SMITH = 5
    TOKE = 6


class EventOption:

    def __init__(self, text, label, disabled=False, choice_index=None):
        self.text = text
        self.label = label
        self.disabled = disabled
        self.choice_index = choice_index

    @classmethod
    def from_json(cls, json_object):
        text = json_object.get("text")
        label = json_object.get("label")
        disabled = json_object.get("disabled")
        choice_index = json_object.get("choice_index", None)
        return cls(text, label, disabled, choice_index)


class Screen:

    SCREEN_TYPE = ScreenType.NONE

    def __init__(self):
        self.screen_type = type(self).SCREEN_TYPE

    @classmethod
    def from_json(cls, json_object):
        return cls()


class ChestScreen(Screen):

    SCREEN_TYPE = ScreenType.CHEST

    def __init__(self, chest_type, chest_open):
        super().__init__()
        self.chest_type = chest_type
        self.chest_open = chest_open

    @classmethod
    def from_json(cls, json_object):
        java_chest_class_name = json_object.get("chest_type")
        if java_chest_class_name == "SmallChest":
            chest_type = ChestType.SMALL
        elif java_chest_class_name == "MediumChest":
            chest_type = ChestType.MEDIUM
        elif java_chest_class_name == "LargeChest":
            chest_type = ChestType.LARGE
        elif java_chest_class_name == "BossChest":
            chest_type = ChestType.BOSS
        else:
            chest_type = ChestType.UNKNOWN
        chest_open = json_object.get("chest_open")
        return cls(chest_type, chest_open)


class EventScreen(Screen):

    SCREEN_TYPE = ScreenType.EVENT

    def __init__(self, name, event_id, body_text=""):
        super().__init__()
        self.event_name = name
        self.event_id = event_id
        self.body_text = body_text
        self.options = []

    @classmethod
    def from_json(cls, json_object):
        event = cls(json_object["event_name"], json_object["event_id"], json_object["body_text"])
        for json_option in json_object["options"]:
            event.options.append(EventOption.from_json(json_option))
        return event


class ShopRoomScreen(Screen):

    SCREEN_TYPE = ScreenType.SHOP_ROOM


class RestScreen(Screen):

    SCREEN_TYPE = ScreenType.REST

    def __init__(self, has_rested, rest_options):
        super().__init__()
        self.has_rested = has_rested
        self.rest_options = rest_options

    @classmethod
    def from_json(cls, json_object):
        rest_options = [RestOption[option.upper()] for option in json_object.get("rest_options")]
        return cls(json_object.get("has_rested"), rest_options)


class CardRewardScreen(Screen):

    SCREEN_TYPE = ScreenType.CARD_REWARD

    def __init__(self, cards, can_bowl, can_skip):
        super().__init__()
        self.cards = cards
        self.can_bowl = can_bowl
        self.can_skip = can_skip

    @classmethod
    def from_json(cls, json_object):
        cards = [Card.from_json(card) for card in json_object.get("cards")]
        can_bowl = json_object.get("bowl_available")
        can_skip = json_object.get("skip_available")
        return cls(cards, can_bowl, can_skip)


class CombatReward:

    def __init__(self, reward_type, gold=0, relic=None, potion=None, link=None):
        self.reward_type = reward_type
        self.gold = gold
        self.relic = relic
        self.potion = potion
        self.link = link

    def __eq__(self, other):
        return self.reward_type == other.reward_type and self.gold == other.gold \
               and self.relic == other.relic and self.potion == other.potion and self.link == other.link


class CombatRewardScreen(Screen):

    SCREEN_TYPE = ScreenType.COMBAT_REWARD

    def __init__(self, rewards):
        super().__init__()
        self.rewards = rewards

    @classmethod
    def from_json(cls, json_object):
        rewards = []
        for json_reward in json_object.get("rewards"):
            reward_type = RewardType[json_reward.get("reward_type")]
            if reward_type in [RewardType.GOLD, RewardType.STOLEN_GOLD]:
                rewards.append(CombatReward(reward_type, gold=json_reward.get("gold")))
            elif reward_type == RewardType.RELIC:
                rewards.append(CombatReward(reward_type, relic=Relic.from_json(json_reward.get("relic"))))
            elif reward_type == RewardType.POTION:
                rewards.append(CombatReward(reward_type, potion=Potion.from_json(json_reward.get("potion"))))
            elif reward_type == RewardType.SAPPHIRE_KEY:
                rewards.append(CombatReward(reward_type, link=Relic.from_json(json_reward.get("link"))))
            else:
                rewards.append(CombatReward(reward_type))
        return cls(rewards)


class MapScreen(Screen):

    SCREEN_TYPE = ScreenType.MAP

    def __init__(self, current_node, next_nodes, boss_available):
        super().__init__()
        self.current_node = current_node
        self.next_nodes = next_nodes
        self.boss_available = boss_available

    @classmethod
    def from_json(cls, json_object):
        current_node_json = json_object.get("current_node", None)
        next_nodes_json = json_object.get("next_nodes", None)
        boss_available = json_object.get("boss_available")
        if current_node_json is not None:
            current_node = Node.from_json(current_node_json)
        else:
            current_node = None
        if next_nodes_json is not None:
            next_nodes = [Node.from_json(node) for node in next_nodes_json]
        else:
            next_nodes = []
        return cls(current_node, next_nodes, boss_available)


class BossRewardScreen(Screen):

    SCREEN_TYPE = ScreenType.BOSS_REWARD

    def __init__(self, relics):
        super().__init__()
        self.relics = relics

    @classmethod
    def from_json(cls, json_object):
        relics = [Relic.from_json(relic) for relic in json_object.get("relics")]
        return cls(relics)


class ShopScreen(Screen):

    SCREEN_TYPE = ScreenType.SHOP_SCREEN

    def __init__(self, cards, relics, potions, purge_available, purge_cost):
        super().__init__()
        self.cards = cards
        self.relics = relics
        self.potions = potions
        self.purge_available = purge_available
        self.purge_cost = purge_cost

    @classmethod
    def from_json(cls, json_object):
        cards = [Card.from_json(card) for card in json_object.get("cards")]
        relics = [Relic.from_json(relic) for relic in json_object.get("relics")]
        potions = [Potion.from_json(potion) for potion in json_object.get("potions")]
        purge_available = json_object.get("purge_available")
        purge_cost = json_object.get("purge_cost")
        return cls(cards, relics, potions, purge_available, purge_cost)


class GridSelectScreen(Screen):

    SCREEN_TYPE = ScreenType.GRID

    def __init__(self, cards, selected_cards, num_cards, any_number, confirm_up, for_upgrade, for_transform, for_purge):
        super().__init__()
        self.cards = cards
        self.selected_cards = selected_cards
        self.num_cards = num_cards
        self.any_number = any_number
        self.confirm_up = confirm_up
        self.for_upgrade = for_upgrade
        self.for_transform = for_transform
        self.for_purge = for_purge

    @classmethod
    def from_json(cls, json_object):
        cards = [Card.from_json(card) for card in json_object.get("cards")]
        selected_cards = [Card.from_json(card) for card in json_object.get("selected_cards")]
        num_cards = json_object.get("num_cards")
        any_number = json_object.get("any_number", False)
        confirm_up = json_object.get("confirm_up")
        for_upgrade = json_object.get("for_upgrade")
        for_transform = json_object.get("for_transform")
        for_purge = json_object.get("for_purge")
        return cls(cards, selected_cards, num_cards, any_number, confirm_up, for_upgrade, for_transform, for_purge)


class HandSelectScreen(Screen):

    SCREEN_TYPE = ScreenType.HAND_SELECT

    def __init__(self, cards, selected, num_cards, can_pick_zero):
        super().__init__()
        self.cards = cards
        self.selected_cards = selected
        self.num_cards = num_cards
        self.can_pick_zero = can_pick_zero

    @classmethod
    def from_json(cls, json_object):
        cards = [Card.from_json(card) for card in json_object.get("hand")]
        selected_cards = [Card.from_json(card) for card in json_object.get("selected")]
        num_cards = json_object.get("max_cards")
        can_pick_zero = json_object.get("can_pick_zero")
        return cls(cards, selected_cards, num_cards, can_pick_zero)


class GameOverScreen(Screen):

    SCREEN_TYPE = ScreenType.GAME_OVER

    def __init__(self, score, victory):
        super().__init__()
        self.score = score
        self.victory = victory

    @classmethod
    def from_json(cls, json_object):
        return cls(json_object.get("score"), json_object.get("victory"))


class CompleteScreen(Screen):

    SCREEN_TYPE = ScreenType.COMPLETE


SCREEN_CLASSES = {
    ScreenType.EVENT: EventScreen,
    ScreenType.CHEST: ChestScreen,
    ScreenType.SHOP_ROOM: ShopRoomScreen,
    ScreenType.REST: RestScreen,
    ScreenType.CARD_REWARD: CardRewardScreen,
    ScreenType.COMBAT_REWARD: CombatRewardScreen,
    ScreenType.MAP: MapScreen,
    ScreenType.BOSS_REWARD: BossRewardScreen,
    ScreenType.SHOP_SCREEN: ShopScreen,
    ScreenType.GRID: GridSelectScreen,
    ScreenType.HAND_SELECT: HandSelectScreen,
    ScreenType.GAME_OVER: GameOverScreen,
    ScreenType.COMPLETE: CompleteScreen,
    ScreenType.NONE: Screen
}


def screen_from_json(screen_type, json_object):
    return SCREEN_CLASSES[screen_type].from_json(json_object)
