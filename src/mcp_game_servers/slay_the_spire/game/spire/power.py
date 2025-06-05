from mcp_game_servers.slay_the_spire.game.spire.card import Card

class Power:

    def __init__(self, power_id, name, description, amount, damage=0, misc=0, just_applied=False, card=None):
        self.power_id = power_id
        self.power_name = name
        self.description = description
        self.amount = amount
        self.damage = damage
        self.misc = misc
        self.just_applied = just_applied
        self.card = card

    @classmethod
    def from_json(cls, json_object):
        power_id = json_object["id"]
        name = json_object["name"]
        description = json_object["description"]
        amount = json_object["amount"]
        damage = json_object.get("damage", 0)
        misc = json_object.get("misc", 0)
        just_applied = json_object.get("just_applied", False)
        card = json_object.get("card", None)
        if card is not None:
            card = Card.from_json(card)
        return cls(power_id, name, description, amount, damage, misc, just_applied, card)

    def __eq__(self, other):
        return self.power_id == other.power_id and self.amount == other.amount
