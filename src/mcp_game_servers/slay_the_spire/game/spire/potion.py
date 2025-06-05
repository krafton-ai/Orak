class Potion:

    def __init__(self, potion_id, name, can_use, can_discard, requires_target, price=0):
        self.potion_id = potion_id
        self.name = name
        self.can_use = can_use
        self.can_discard = can_discard
        self.requires_target = requires_target
        self.price = price

    def __eq__(self, other):
        return other.potion_id == self.potion_id

    @classmethod
    def from_json(cls, json_object):
        return cls(
            potion_id=json_object.get("id"),
            name=json_object.get("name"),
            can_use=json_object.get("can_use", False),
            can_discard=json_object.get("can_discard", False),
            requires_target=json_object.get("requires_target", False),
            price=json_object.get("price", 0)
        )
