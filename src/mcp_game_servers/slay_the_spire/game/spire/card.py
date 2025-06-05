from enum import Enum


class CardType(Enum):
    ATTACK = 1
    SKILL = 2
    POWER = 3
    STATUS = 4
    CURSE = 5


class CardRarity(Enum):
    BASIC = 1
    COMMON = 2
    UNCOMMON = 3
    RARE = 4
    SPECIAL = 5
    CURSE = 6


class Card:
    def __init__(self, card_id, name, description, card_type, rarity, upgrades=0, has_target=False, cost=0, uuid="", misc=0, price=0, is_playable=False, exhausts=False):
        self.card_id = card_id
        self.name = name
        self.type = card_type
        self.rarity = rarity
        self.upgrades = upgrades
        self.has_target = has_target
        self.cost = cost
        self.uuid = uuid
        self.misc = misc
        self.price = price
        self.is_playable = is_playable
        self.exhausts = exhausts
        self.description = description

    @classmethod
    def from_json(cls, json_object):
        return cls(
            card_id=json_object["id"],
            name=json_object["name"],
            description=json_object["description"],
            card_type=CardType[json_object["type"]],
            rarity=CardRarity[json_object["rarity"]],
            upgrades=json_object["upgrades"],
            has_target=json_object["has_target"],
            cost=json_object["cost"],
            uuid=json_object["uuid"],
            misc=json_object.get("misc", 0),
            price=json_object.get("price", 0),
            is_playable=json_object.get("is_playable", False),
            exhausts=json_object.get("exhausts", False)
        )

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __str__(self):
        return f"Card(Name: {self.name}, Id: {self.card_id}, Type: {self.type}, Rarity: {self.rarity}, Upgrades: {self.upgrades}, Cost: {self.cost})"
    
    def __repr__(self):
        return self.__str__()
