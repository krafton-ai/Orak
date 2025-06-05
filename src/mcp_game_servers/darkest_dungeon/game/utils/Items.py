import math
import time
from .Controls import Controller

EmptySlots = []


def buy_provisions(dungeon_name, length, difficulty, debug):
    c = Controller(debug)
    provisions = Provisions[dungeon_name][length]
    c.write(c.right_stick_up)

    c.write(c.a, presses=provisions['food'])
    c.write(c.left_stick_right)
    c.write(c.a, presses=provisions['shovel'])
    c.write(c.left_stick_right)
    c.write(c.a, presses=provisions['antivenom'])
    c.write(c.left_stick_right)
    c.write(c.a, presses=provisions['bandage'])
    c.write(c.left_stick_right)
    c.write(c.a, presses=provisions['medicinal_herbs'])
    c.write(c.left_stick_right)
    c.write(c.a, presses=provisions['skeleton_key'])
    c.write(c.left_stick_right)
    c.write(c.a, presses=provisions['holy_water'])
    c.write(c.left_stick_down)
    c.write(c.left_stick_left, presses=6)
    c.write(c.left_stick_right)
    c.write(c.a, presses=provisions['torch'])

    c.write(c.back)
    time.sleep(5)  # need to make sure to wait until dungeon is loaded
    c.write(c.a)


class Inventory:
    def __init__(self, raid_info):
        global EmptySlots
        items = []
        _items = raid_info['party']['inventory']['items']
        if len(EmptySlots) > 0 + len(_items) > 16:
            print('attempting to correct inventory.empty_slots!')
            EmptySlots.sort()
            while len(EmptySlots) + len(_items) > 16 and len(EmptySlots) > 0:
                EmptySlots.pop(0)
        self.empty_slots = EmptySlots
        print(f'empty_slots: {self.empty_slots}')
        for index, value in _items.items():
            offset = sum(empty_slot <= int(index) for empty_slot in self.empty_slots)
            item_slot = offset + int(index)
            items.append(Item(value['id'], value['type'], value['amount'], item_slot))
        self.items = items
        self.provision_totals = self.get_provision_totals(self.items)
        dungeon = raid_info['raid_instance']['dungeon']
        dungeon_length = raid_info['raid_instance']['length']
        self.starting_provisions = Provisions[dungeon][dungeon_length]
        self.stacksToKeep = self.get_number_of_stacks(self.starting_provisions)
        self.numberOfStacks = self.get_number_of_stacks(self.provision_totals)

    @staticmethod
    def get_number_of_stacks(provisions_dict):
        return {'food': math.ceil(provisions_dict['food']/Items['food']['full_stack']),
                'shovel': math.ceil(provisions_dict['shovel']/Items['shovel']['full_stack']),
                'antivenom': math.ceil(provisions_dict['antivenom']/Items['antivenom']['full_stack']),
                'bandage': math.ceil(provisions_dict['bandage']/Items['bandage']['full_stack']),
                'medicinal_herbs':
                    math.ceil(provisions_dict['medicinal_herbs']/Items['medicinal_herbs']['full_stack']),
                'skeleton_key': math.ceil(provisions_dict['skeleton_key']/Items['skeleton_key']['full_stack']),
                'holy_water': math.ceil(provisions_dict['holy_water']/Items['holy_water']['full_stack']),
                'torch': math.ceil(provisions_dict['torch']/Items['torch']['full_stack'])}

    @staticmethod
    def get_provision_totals(items):
        return {'food': sum(item.quantity if item.name == 'food' else 0 for item in items),
                'shovel': sum(item.quantity if item.name == 'shovel' else 0 for item in items),
                'antivenom': sum(item.quantity if item.name == 'antivenom' else 0 for item in items),
                'bandage': sum(item.quantity if item.name == 'bandage' else 0 for item in items),
                'medicinal_herbs': sum(item.quantity if item.name == 'medicinal_herbs' else 0 for item in items),
                'skeleton_key': sum(item.quantity if item.name == 'skeleton_key' else 0 for item in items),
                'holy_water': sum(item.quantity if item.name == 'holy_water' else 0 for item in items),
                'torch': sum(item.quantity if item.name == 'torch' else 0 for item in items)}


class Item:
    def __init__(self, name, item_type, quantity, item_slot=None):
        if item_type == 'quest_item':
            name = 'potent_salve' if name == 'antivenom' else name
            name = 'consecrated_essence' if name == 'holy_water' else name
            name = 'medicine' if name == 'medicines' else name
            name = 'pineal_gland' if name == 'eldritch_lantern' else name
            name = 'ancestors_relic' if name == 'ancestors_crate' else name
            name = 'pick-axe' if name == 'pickaxe' else name
        self.name = item_type if item_type == 'gold' or item_type == 'journal_page' else 'food' if name == '' else name
        self.quantity = quantity
        self.item_slot = None if item_slot is None else int(item_slot)
        self.type = Items[self.name]['type']
        self.rating = Items[self.name]['rating'] if self.type == 'trinket' else None
        self.full_stack = Items[self.name]['full_stack'] if 'full_stack' in Items[self.name] else 1
        if 'value' in Items[self.name] and Items[self.name]['value'] is not None:
            if self.type == 'trinket' and self.rating >= 6 and Items[self.name]['value'] < 2500:
                self.value = 2500
            elif self.type == 'trinket' and Items[self.name]['value'] == 750:
                self.value = 350
            else:
                self.value = Items[self.name]['value'] * quantity
        else:
            self.value = None


Provisions = {
    # 1 - short, 2 - medium, 3 - long
    # ruins = crypts
    "crypts": {1: {'food': 12, 'shovel': 2, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 1,
                   'skeleton_key': 3, 'holy_water': 1, 'torch': 8},
               2: {'food': 20, 'shovel': 3, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 1,
                   'skeleton_key': 4, 'holy_water': 2, 'torch': 11},
               3: {'food': 28, 'shovel': 4, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 0,
                   'skeleton_key': 5, 'holy_water': 2, 'torch': 15}},
    # future - can't remember if these enemies have annoying debuffs at higher difficulty levels but check and buy more
    #           medicinal herbs accordingly
    "warrens": {1: {'food': 12, 'shovel': 2, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 2,
                    'skeleton_key': 2, 'holy_water': 1, 'torch': 9},
                2: {'food': 18, 'shovel': 3, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 2,
                    'skeleton_key': 3, 'holy_water': 2, 'torch': 12},
                3: {'food': 24, 'shovel': 4, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 3,
                    'skeleton_key': 4, 'holy_water': 2, 'torch': 16}},
    "weald": {1: {'food': 12, 'shovel': 4, 'antivenom': 1, 'bandage': 2, 'medicinal_herbs': 1,
                  'skeleton_key': 2, 'holy_water': 0, 'torch': 8},
              2: {'food': 20, 'shovel': 5, 'antivenom': 1, 'bandage': 2, 'medicinal_herbs': 1,
                  'skeleton_key': 3, 'holy_water': 0, 'torch': 11},
              3: {'food': 28, 'shovel': 6, 'antivenom': 2, 'bandage': 3, 'medicinal_herbs': 1,
                  'skeleton_key': 4, 'holy_water': 0, 'torch': 15}},
    # future - make it buy bandages for the cove depending on difficulty levels
    "cove": {1: {'food': 12, 'shovel': 4, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 3,
                 'skeleton_key': 2, 'holy_water': 0, 'torch': 8},
             2: {'food': 20, 'shovel': 5, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 4,
                 'skeleton_key': 3, 'holy_water': 0, 'torch': 11},
             3: {'food': 28, 'shovel': 6, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 4,
                 'skeleton_key': 4, 'holy_water': 0, 'torch': 15}},
    "courtyard": {},
    "farmstead": {},
    "darkest_dungeon": {},
    "tutorial": {1: {'food': 0, 'shovel': 0, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 0,
                     'skeleton_key': 0, 'holy_water': 0, 'torch': 0}},
    # "crypts": {1: {'food': 4, 'shovel': 2, 'antivenom': 0, 'bandage': 0, 'medicinal_herbs': 0,
    #                'skeleton_key': 2, 'holy_water': 0, 'torch': 6},}  # tutorial 2
}


Items = {
    # Provisions
    "food":      {"type": 'provision', "value": 5, "full_stack": 12,
                  "thumb": {'inv_provision+_0.png', 'inv_provision+_1.png', 'inv_provision+_2.png',
                            'inv_provision+_3.png'}},
    "shovel":    {"type": 'provision', "value": 25, "full_stack": 4, "thumb": {'inv_supply+shovel.png'}},
    "antivenom": {"type": 'provision', "value": 15, "full_stack": 6, "thumb": {'inv_supply+antivenom.png'}},
    "bandage":   {"type": 'provision', "value": 15, "full_stack": 6, "thumb": {'inv_supply+bandage.png'}},
    "medicinal_herbs": {"type": 'provision', "value": 20, "full_stack": 6, "thumb": {'inv_supply+medicinal_herbs.png'}},
    "skeleton_key":    {"type": 'provision', "value": 20, "full_stack": 6, "thumb": {'inv_supply+skeleton_key.png'}},
    "holy_water":      {"type": 'provision', "value": 15, "full_stack": 6, "thumb": {'inv_supply+holy_water.png'}},
    "laudanum":    {"type": 'supply', "value": 10, "full_stack": 6, "thumb": {'inv_supply+laudanum.png'}},
    "torch":       {"type": 'provision', "value": 5, "full_stack": 8, "thumb": {'inv_supply+torch.png'}},
    "firewood":    {"type": 'supply', "value": None, "full_stack": 1, "thumb": {'inv_supply+firewood.png'}},
    "dog_treats":  {"type": 'supply', "value": 0, "full_stack": 2, "thumb": {'inv_supply+dog_treats.png'}},
    "the_blood":   {"type": 'supply', "value": 450, "full_stack": 6, "thumb": {'inv_estate+the_blood.png'}},
    "the_cure":    {"type": 'supply', "value": None, "full_stack": 6, "thumb": {'inv_estate+the_cure.png'}},
    "aegis_scale": {"type": 'supply', "value": None, "full_stack": 4, "thumb": {'inv_estate+snake_scale.png'}},
    "shard_dust":  {"type": 'supply', "value": None, "full_stack": 99, "thumb": {'inv_supply+spice.png'}},

    # Loot
    "gold":     {"type": 'gold', "value": 1, "full_stack": 1750,
                 "thumb": {'inv_gold+_0.png', 'inv_gold+_1.png', 'inv_gold+_2.png', 'inv_gold+_3.png'}},
    "citrine":  {"type": 'gem', "value": 150, "full_stack": 5, "thumb": {'inv_gem+citrine.png'}},
    "jade":     {"type": 'gem', "value": 375, "full_stack": 5, "thumb": {'inv_gem+jade.png'}},
    "onyx":     {"type": 'gem', "value": 500, "full_stack": 5, "thumb": {'inv_gem+onyx.png'}},
    "emerald":  {"type": 'gem', "value": 750, "full_stack": 5, "thumb": {'inv_gem+emerald.png'}},
    "sapphire": {"type": 'gem', "value": 1000, "full_stack": 5, "thumb": {'inv_gem+sapphire.png'}},
    "ruby":     {"type": 'gem', "value": 1250, "full_stack": 5, "thumb": {'inv_gem+ruby.png'}},
    "jute_tapestry":          {"type": 'gem', "value": 4500, "full_stack": 1, "thumb": {'inv_gem+ancient_idol.png'}},
    "trapezohedron": {"type": 'gem', "value": 3500, "full_stack": 1, "thumb": {'inv_gem+trapezohedron.png'}},
    "minor_antique":   {"type": 'gem', "value": 500, "full_stack": 20, "thumb": {'inv_gem+antiqrelicsmall.png'}},
    "rare_antique":    {"type": 'gem', "value": 1250, "full_stack": 5, "thumb": {'inv_gem+antiqrelic.png'}},
    "consecrated_pew": {"type": 'gem', "value": 2500, "full_stack": 1, "thumb": {'inv_gem+pewrelic.png'}},
    "journal_page":    {"type": 'journal_page', "value": 0, "full_stack": 1, "thumb": {'inv_journal_page.png'}},
    "comet_shard": {"type": 'special', "value": None, "full_stack": 99, "thumb": {'inv_shard+.png'}},

    # Heirlooms
    "bust":      {"type": 'heirloom', "value": None, "full_stack": 6, "thumb": {'inv_heirloom+bust.png'}},
    "portrait":  {"type": 'heirloom', "value": None, "full_stack": 3, "thumb": {'inv_heirloom+portrait.png'}},
    "deed":      {"type": 'heirloom', "value": None, "full_stack": 6, "thumb": {'inv_heirloom+deed.png'}},
    "crest":     {"type": 'heirloom', "value": None, "full_stack": 12, "thumb": {'inv_heirloom+crest.png'}},
    "blueprint": {"type": 'special',  "value": None, "full_stack": 1, "thumb": {'inv_heirloom+blueprint.png'}},
    "crimson_court_invitation_A":    {"type": 'invitation', "value": None, "full_stack": 100,
                                      "thumb": {'inv_estate_currency+crimson_court_invitation_A.png'}},
    "crimson_court_invitation_B": {"type": 'invitation', "value": None, "full_stack": 100,
                                   "thumb": {'inv_estate_currency+crimson_court_invitation_B.png'}},
    "crimson_court_invitation_C":  {"type": 'invitation', "value": None, "full_stack": 100,
                                    "thumb": {'inv_estate_currency+crimson_court_invitation_C.png'}},
    "memory": {"type": 'special', "value": 1, "full_stack": None, "thumb": {'inv_heirloom+memory.png'}},

    # Quest
    "consecrated_essence": {"type": 'quest', "value": None, "full_stack": 1,
                            "thumb": {'inv_quest_item+holy_water.png'}},
    "potent_salve":    {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+antivenom.png'}},
    "pick-axe":        {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+pickaxe.png'}},
    "pineal_gland":    {"type": 'quest', "value": None, "full_stack": 1,
                        "thumb": {'inv_quest_item+eldritch_lantern.png'}},
    "holy_relic":      {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+holy_relic.png'}},
    "medicine":        {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+medicines.png'}},
    "grain_sack":      {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+grain_sack.png'}},
    "ancestors_relic": {"type": 'quest', "value": None, "full_stack": 1,
                        "thumb": {'inv_quest_item+ancestors_crate.png'}},
    "hand_of_glory":   {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+beacon_light.png'}},
    "pitch-soaked_torch": {"type": 'quest', "value": None, "full_stack": 3,
                           "thumb": {'inv_quest_item+torch_quest.png'}},
    "red_key":    {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+key1.png'}},
    "yellow_key": {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+key2.png'}},
    "green_key":  {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+key3.png'}},
    "blue_key":   {"type": 'quest', "value": None, "full_stack": 1, "thumb": {'inv_quest_item+key4.png'}},

    # (Very) Common Trinkets
    "accuracy_stone":   {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+accuracy_stone.png'}},
    "bleed_charm":      {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'dodge': -2},
                         "thumb": {'inv_trinket+bleed_charm.png'}},
    "bleed_stone":      {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+bleed_stone.png'}},
    "blight_charm":     {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'dodge': -2},
                         "thumb": {'inv_trinket+blight_charm.png'}},
    "blight_stone":     {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+blight_stone.png'}},
    "critical_stone":   {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+critical_stone.png'}},
    "debuff_charm":     {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'dodge': -2},
                         "thumb": {'inv_trinket+debuff_charm.png'}},
    "debuff_stone":     {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+debuff_stone.png'}},
    "disease_charm":    {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'dodge': -2},
                         "thumb": {'inv_trinket+disease_charm.png'}},
    "dodge_stone":      {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+dodge_stone.png'}},
    "health_stone":     {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+health_stone.png'}},
    "move_charm":       {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'dodge': -2},
                         "thumb": {'inv_trinket+move_charm.png'}},
    "move_stone":       {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+move_stone.png'}},
    "protection_stone": {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+protection_stone.png'}},
    "stun_charm":       {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'dodge': -2},
                         "thumb": {'inv_trinket+stun_charm.png'}},
    "stun_stone":       {"type": 'trinket', "value": 750, "rating": 0, "keep": 0, "neg": {'spd': -1},
                         "thumb": {'inv_trinket+stun_stone.png'}},

    # Common Trinkets
    "archers_ring":         {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "neg": {'spd': -1},
                             "thumb": {'inv_trinket+archers_ring.png'}},
    "bloodied_fetish":      {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+bloodied_fetish.png'}},
    "book_of_intuition":    {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "neg": {'spd': -1},
                             "thumb": {'inv_trinket+book_of_intuition.png'}},
    "caution_cloak":        {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "neg": {'spd': -10},
                             "thumb": {'inv_trinket+caution_cloak.png'}},
    "damage_stone":         {"type": 'trinket', "value": 1780, "rating": 7, "keep": 3, "neg": {'dodge': -4},
                             "pos": {'dmg': 10}, "thumb": {'inv_trinket+damage_stone.png'}},
    "dazzling_charm":       {"type": 'trinket', "value": 1780, "rating": 6, "keep": 2, "neg": None,
                             "pos": {'stun': 10}, "thumb": {'inv_trinket+dazzling_charm.png'}},
    "deteriorating_bracer": {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "neg": None,
                             "thumb": 'inv_trinket+deteriorating_bracer.png'},
    "reckless_charm":       {"type": 'trinket', "value": 650, "rating": 2, "keep": 1, "neg": {'dodge': -2},
                             "pos": {'acc': 5}, "thumb": {'inv_trinket+reckless_charm.png'}},
    "slippery_boots":       {"type": 'trinket', "value": 650, "rating": 1, "keep": 0, "neg": None,
                             "pos": {'dodge': 4}, "thumb": {'inv_trinket+slippery_boots.png'}},
    "snake_oil":            {"type": 'trinket', "value": 1125, "rating": 4, "keep": 1, "neg": None,
                             "pos": {'stress': -10}, "thumb": {'inv_trinket+snake_oil.png'}},
    "speed_stone":          {"type": 'trinket', "value": 1125, "rating": 5, "keep": 2, "neg": None, "pos": {'spd': 1},
                             "thumb": {'inv_trinket+speed_stone.png'}},
    "survival_guide":       {"type": 'trinket', "value": 1780, "rating": 6, "keep": 2, "neg": {'spd': -1},
                             "pos": {'scout': 10, 'trap': 10}, "thumb": {'inv_trinket+survival_guide.png'}},
    "warriors_bracer":      {"type": 'trinket', "value": 1775, "rating": 6, "keep": 2, "neg": {'dodge': -4},
                             "pos": {'melee_dmg': 10}, "thumb": {'inv_trinket+warriors_bracer.png'}},
    "warriors_cap":         {"type": 'trinket', "value": 650, "rating": 3, "keep": 1, "neg": None, "pos": {'acc': 5},
                             "thumb": {'inv_trinket+warriors_cap.png'}},

    # Common (Hero) Trinkets
    "padlock_1":              {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'abomination',
                               "thumb": {'inv_trinket+padlock_1.png'}},  # lock_of_patience
    "antiq_1":                {"type": 'trinket', "value": 650, "rating": 3, "keep": 1, "hero_class": 'antiquarian',
                               "pos": {'dodge': 10}, "thumb": {'inv_trinket+antiq_1.png'}},  # bag_of_marbles
    "sturdy_greaves":         {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'arbalest',
                               "neg": {'spd': -1}, "thumb": {'inv_trinket+sturdy_greaves.png'}},
    "vengeful_greaves":       {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'arbalest',
                               "thumb": {'inv_trinket+vengeful_greaves.png'}},
    "agile_talon":            {"type": 'trinket', "value": 650, "rating": 3, "keep": 1, "hero_class": 'bounty_hunter',
                               "pos": {'spd': 1, 'dodge': 4}, "thumb": {'inv_trinket+agile_talon.png'}},
    "unmovable_helmet":       {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'bounty_hunter',
                               "thumb": {'inv_trinket+unmovable_helmet.png'}},
    "defenders_seal":         {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'crusader',
                               "thumb": {'inv_trinket+defenders_seal.png'}},
    "knights_crest":          {"type": 'trinket', "value": 1125, "rating": 2, "keep": 0, "hero_class": 'crusader',
                               "pos": {'hp':10}, "thumb": {'inv_trinket+knights_crest.png'}},
    "swordsmans_crest":       {"type": 'trinket', "value": 1125, "rating": 5, "keep": 1, "hero_class": 'crusader',
                               "pos": {'dmg': 10}, "thumb": {'inv_trinket+swordsmans_crest.png'}},
    "flag_5":                 {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'flagellant',
                               "thumb": {'inv_trinket+flag_5.png'}},  # heartburst_hood
    "quickening_satchel":     {"type": 'trinket', "value": 650, "rating": 4, "keep": 1, "hero_class": 'grave_robber',
                               "pos": {'spd': 2}, "thumb": {'inv_trinket+quickening_satchel.png'}},
    "stunning_satchel":       {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'grave_robber',
                               "thumb": {'inv_trinket+stunning_satchel.png'}},  # sickening_satchel
    "bleeding_pendant":       {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'hellion',
                               "thumb": {'inv_trinket+bleeding_pendant.png'}},
    "selfish_pendant":        {"type": 'trinket', "value": 1125, "rating": 4, "keep": 1, "hero_class": 'hellion',
                               "pos": {'stress': -15}, "thumb": {'inv_trinket+selfish_pendant.png'}},
    "drifters_buckle":        {"type": 'trinket', "value": 650, "rating": 1, "keep": 0, "hero_class": 'highwayman',
                               "thumb": {'inv_trinket+drifters_buckle.png'}},
    "flashfire_gunpowder":    {"type": 'trinket', "value": 650, "rating": 1, "keep": 0, "hero_class": 'highwayman',
                               "thumb": {'inv_trinket+flashfire_gunpowder.png'}},
    "cursed_buckle":          {"type": 'trinket', "value": 650, "rating": 1, "keep": 0, "hero_class": 'highwayman',
                               "thumb": {'inv_trinket+cursed_buckle.png'}},  # stalwart_buckle
    "agility_whistle":        {"type": 'trinket', "value": 1125, "rating": 3, "keep": 1, "hero_class": 'houndmaster',
                               "pos": {'spd': 1, 'dodge': 4}, "thumb": {'inv_trinket+agility_whistle.png'}},
    "scouting_whistle":       {"type": 'trinket', "value": 1775, "rating": 8, "keep": 2, "hero_class": 'houndmaster',
                               "pos": {'scout': 15, 'trap': 20},  # 20% scouting if torch below 51, otherwise it's 15!
                               "thumb": {'inv_trinket+scouting_whistle.png'}},
    "bloody_dice":            {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'jester',
                               "thumb": {'inv_trinket+bloody_dice.png'}},
    "lucky_dice":             {"type": 'trinket', "value": 650, "rating": 3, "keep": 0, "hero_class": 'jester',
                               "thumb": {'inv_trinket+lucky_dice.png'}},
    "healing_armlet":         {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'leper',
                               "thumb": {'inv_trinket+healing_armlet.png'}},
    "selfish_armlet":         {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'leper',
                               "thumb": {'inv_trinket+selfish_armlet.png'}},  # redemption_armlet
    "cleansing_eyepatch":     {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'man-at-arms',
                               "neg": {'dodge': -2}, "thumb": {'inv_trinket+cleansing_eyepatch.png'}},
    "sly_eyepatch":           {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'man-at-arms',
                               "thumb": {'inv_trinket+sly_eyepatch.png'}},
    "sturdy_boots":           {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'musketeer',
                               "neg": {'spd': -1}, "thumb": {'inv_trinket+sturdy_boots.png'}},
    "vengeful_boots":         {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'musketeer',
                               "thumb": {'inv_trinket+vengeful_boots.png'}},
    "eldritch_killing_incense": {"type": 'trinket', "value": 650, "rating": 4, "keep": 0, "hero_class": 'occultist',
                                 "thumb": {'inv_trinket+eldritch_killing_incense.png'}},
    "evasion_incense":        {"type": 'trinket', "value": 650, "rating": 2, "keep": 0, "hero_class": 'occultist',
                               "neg": {'spd': -1}, "pos": {'dodge': 8}, "thumb": {'inv_trinket+evasion_incense.png'}},
    "diseased_herb":          {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'plague_doctor',
                               "thumb": {'inv_trinket+diseased_herb.png'}},
    "rotgut_censer":          {"type": 'trinket', "value": 1125, "rating": 2, "keep": 0, "hero_class": 'plague_doctor',
                               "neg": {'hp': -5}, "pos": {'acc': 8}, "thumb": {'inv_trinket+rotgut_censer.png'}},
    "witchs_vial":            {"type": 'trinket', "value": 1780, "rating": 5, "keep": 1, "hero_class": 'plague_doctor',
                               "pos": {'stun_chance': 15}, "thumb": {'inv_trinket+witchs_vial.png'}},
    "sb_1":                   {"type": 'trinket', "value": None, "rating": 0, "keep": 1, "hero_class": 'shieldbreaker',
                               "thumb": {'inv_trinket+sb_1.png'}},  # venomous_vial
    "recovery_chalice":       {"type": 'trinket', "value": 650, "rating": 0, "keep": 0, "hero_class": 'vestal',
                               "neg": {'hp': -5}, "thumb": {'inv_trinket+recovery_chalice.png'}},  # virtuous_chalice

    # Uncommon Trinkets
    "bleed_amulet":         {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+bleed_amulet.png'}},
    "blight_amulet":        {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+blight_amulet.png'}},
    "blood_charm":          {"type": 'trinket', "value": 1500, "rating": 2, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+blood_charm.png'}},
    "bloodthirst_ring":     {"type": 'trinket', "value": 1500, "rating": 3, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+bloodthirst_ring.png'}},
    "book_of_constitution": {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": {'spd': -1},
                             "thumb": {'inv_trinket+book_of_constitution.png'}},
    "book_of_holiness":     {"type": 'trinket', "value": 1500, "rating": 4, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+book_of_holiness.png'}},
    "book_of_rage":         {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+book_of_rage.png'}},
    "book_of_relaxation":   {"type": 'trinket', "value": 1500, "rating": 4, "keep": 1, "neg": {'dodge': -4},
                             "pos": {'stress': -10, 'acc': 4}, "thumb": {'inv_trinket+book_of_relaxation.png'}},
    "camouflage_cloak":     {"type": 'trinket', "value": 1500, "rating": 6, "keep": 1, "pos": {'dodge': 15},
                             "req": {'sun': 75}, "thumb": {'inv_trinket+camouflage_cloak.png'}},
    "calming_crystal":      {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": {'spd': -1},
                             "thumb": {'inv_trinket+calming_crystal.png'}},
    "chirurgeons_charm":    {"type": 'trinket', "value": 1500, "rating": 8, "keep": 2, "neg": None,
                             "pos": {'heal': 15}, "thumb": {'inv_trinket+chirurgeons_charm.png'}},
    "dark_bracer":          {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": {'dmg': -10},
                             "thumb": {'inv_trinket+dark_bracer.png'}},
    "debuff_amulet":        {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": {'dodge': -4},
                             "thumb": {'inv_trinket+debuff_amulet.png'}},
    "gamblers_charm":       {"type": 'trinket', "value": 1500, "rating": 3, "keep": 0, "neg": None, "pos": {'hp': 15},
                             "thumb": {'inv_trinket+gamblers_charm.png'}},
    "heavy_boots":          {"type": 'trinket', "value": 1500, "rating": 2, "keep": 0, "neg": {'spd': -2},
                             "thumb": {'inv_trinket+heavy_boots.png'}},
    "life_crystal":         {"type": 'trinket', "value": 1500, "rating": 3, "keep": 0, "neg": {'spd': -1},
                             "pos": {'hp': 20}, "thumb": {'inv_trinket+life_crystal.png'}},
    "move_amulet":          {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+move_amulet.png'}},
    "seer_stone":           {"type": 'trinket', "value": 1500, "rating": 7, "keep": 2, "neg": {'spd': -1},
                             "pos": {'scout': 15}, "thumb": {'inv_trinket+seer_stone.png'}},
    "shimmering_cloak":     {"type": 'trinket', "value": 1500, "rating": 3, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+shimmering_cloak.png'}},
    "solar_bracer":        {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": {'dodge': -6, 'crit': -5},
                            "thumb": {'inv_trinket+solar_bracer.png'}},
    "steady_bracer":        {"type": 'trinket', "value": 1500, "rating": 3, "keep": 1, "neg": {'dodge': -2},
                             "pos": {'ranged_acc': 10}, "thumb": {'inv_trinket+steady_bracer.png'}},
    "stun_amulet":          {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": {'dodge': -4},
                             "thumb": {'inv_trinket+stun_amulet.png'}},
    "surgical_gloves":      {"type": 'trinket', "value": 1500, "rating": 5, "keep": 1, "neg": None,
                             "pos": {'melee_acc': 5, 'melee_crit': 8}, "thumb": {'inv_trinket+surgical_glove.png'}},
    "swift_cloak":          {"type": 'trinket', "value": 1500, "rating": 8, "keep": 3, "neg": None, "pos": {'spd': 2},
                             "thumb": {'inv_trinket+swift_cloak.png'}},
    "tenacity_ring":        {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": None,
                             "thumb": {'inv_trinket+tenacity_ring.png'}},
    "worrystone":          {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "neg": {'spd': -1, 'stress': 10},
                            "thumb": {'inv_trinket+worrystone.png'}},

    # Uncommon (Hero) Trinkets
    "padlock_2":               {"type": 'trinket', "value": 1500, "rating": 5, "keep": 1, "hero_class": 'abomination',
                                "pos": {'stun_chance': 20},
                                "thumb": {'inv_trinket+padlock_2.png'}},  # padlock_of_transference
    "padlock_3":               {"type": 'trinket', "value": 1500, "rating": 3, "keep": 1, "hero_class": 'abomination',
                                "neg": {'spd': -1}, "pos": {'prot': 15},
                                "thumb": {'inv_trinket+padlock_3.png'}},  # protective_padlock
    "antiq_2":                 {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'antiquarian',
                                "thumb": {'inv_trinket+antiq_2.png'}},  # bloodcourse_medallion
    "antiq_3":                 {"type": 'trinket', "value": 1500, "rating": 3, "keep": 1, "hero_class": 'antiquarian',
                                "pos": {'prot': 25}, "thumb": {'inv_trinket+antiq_3.png'}},  # carapace_idol
    "medics_greaves":          {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'arbalest',
                                "thumb": {'inv_trinket+medics_greaves.png'}},
    "campers_helmet":          {"type": 'trinket', "value": 1500, "rating": 5, "keep": 1, "hero_class": 'bounty_hunter',
                                "pos": {'scout': 10}, "thumb": {'inv_trinket+campers_helmet.png'}},
    "paralyzers_crest":        {"type": 'trinket', "value": 1500, "rating": 5, "keep": 1, "hero_class": 'crusader',
                                "neg": {'dodge': -2}, "pos": {'stun_chance': 20},
                                "thumb": {'inv_trinket+paralyzers_crest.png'}},
    "flag_4":                  {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'flagellant',
                                "neg": {'bleed': -15}, "thumb": {'inv_trinket+flag_4.png'}},  # resurrections_collar
    "flag_3":                  {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'flagellant',
                                "neg": {'heal': -20}, "thumb": {'inv_trinket+flag_3.png'}},  # punishments_hood
    "seers_satchel":           {"type": 'trinket', "value": 1500, "rating": 2, "keep": 0, "hero_class": 'grave_robber',
                                "neg": {'dodge': -4}, "pos": {'spd': 1},
                                "thumb": {'inv_trinket+seers_satchel.png'}},  # blighting_satchel
    "double-edged_pendant":    {"type": 'trinket', "value": 1500, "rating": 4, "keep": 1, "hero_class": 'hellion',
                                "pos": {'hp': 15}, "thumb": {'inv_trinket+double_edged_pendant.png'}},
    "dodgy_sheath":            {"type": 'trinket', "value": 1500, "rating": 4, "keep": 1, "hero_class": 'highwayman',
                                "neg": {'ranged_acc': -10}, "pos": {'spd': 1, 'dodge': 8},
                                "thumb": {'inv_trinket+dodgy_sheath.png'}},
    "cudgel_weight":           {"type": 'trinket', "value": 1500, "rating": 4, "keep": 1, "hero_class": 'houndmaster',
                                "neg": {'spd': -1}, "pos": {'stun_chance': 25},
                                "thumb": {'inv_trinket+cudgel_weight.png'}},
    "critical_dice":           {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'jester',
                                "thumb": {'inv_trinket+critical_dice.png'}},
    "fortunate_armlet":        {"type": 'trinket', "value": 1500, "rating": 6, "keep": 1, "hero_class": 'leper',
                                "neg": {'stress': 10}, "pos": {'acc': 8, 'crit': 3},
                                "thumb": {'inv_trinket+fortunate_armlet.png'}},
    "longevity_eyepatch":      {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'man-at-arms',
                                "neg": {'spd': -2}, "pos": {'hp': 15}, "thumb": {'inv_trinket+longevity_eyepatch.png'}},
    "medics_boots":            {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'musketeer',
                                "thumb": {'inv_trinket+medics_boots.png'}},
    "cursed_incense":          {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'occultist',
                                "neg": {'hp': -10}, "thumb": {'inv_trinket+cursed_incense.png'}},
    "poisoned_herb":           {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'plague_doctor',
                                "neg": {'hp': -15}, "thumb": {'inv_trinket+poisoned_herb.png'}},
    "sb_2":                    {"type": 'trinket', "value": 1500, "rating": 4, "keep": 1, "hero_class": 'shieldbreaker',
                                "neg": {'stress': 5}, "pos": {'prot': 10},
                                "thumb": {'inv_trinket+sb_2.png'}},  # shimmering_scale
    "sb_3":                    {"type": 'trinket', "value": 1500, "rating": 7, "keep": 1, "hero_class": 'shieldbreaker',
                                "pos": {'spd': 2}, "thumb": {'inv_trinket+sb_3.png'}},  # dancers_footwraps
    "haste_chalice":           {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'vestal',
                                "neg": {'stun_chance': -25}, "thumb": {'inv_trinket+haste_chalice.png'}},
    "youth_chalice":           {"type": 'trinket', "value": 1500, "rating": 0, "keep": 0, "hero_class": 'vestal',
                                "neg": {'dmg': -10}, "thumb": {'inv_trinket+youth_chalice.png'}},

    # Rare Trinkets
    "beast_slayers_ring":    {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'dodge': -8},
                              "thumb": {'inv_trinket+beast_slayers_ring.png'}},
    "berserk_charm":        {"type": 'trinket', "value": 2250, "rating": 6, "keep": 2, "neg": {'stress': 15, 'acc': -5},
                             "pos": {'dmg': 15, 'spd': 3}, "thumb": {'inv_trinket+berserk_charm.png'}},
    "brawlers_gloves":       {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'spd': -1},
                              "thumb": {'inv_trinket+brawlers_gloves.png'}},
    "dark_crown":            {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": None,
                              "thumb": {'inv_trinket+dark_crown.png'}},
    "eldritch_slayers_ring": {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'dodge': -8},
                              "thumb": {'inv_trinket+eldritch_slayers_ring.png'}},
    "fasting_seal":          {"type": 'trinket', "value": 2250, "rating": 5, "keep": 0, "neg": None,
                              "pos": {'dodge': 5}, "thumb": {'inv_trinket+fasting_seal.png'}},
    "feather_crystal":       {"type": 'trinket', "value": 2250, "rating": 8, "keep": 3, "neg": None,
                              "pos": {'spd': 2, 'dodge': 8}, "thumb": {'inv_trinket+feather_crystal.png'}},
    "man_slayers_ring":      {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'dodge': -8},
                              "thumb": {'inv_trinket+man_slayers_ring.png'}},
    "moon_cloak":            {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'stress': 10},
                              "thumb": {'inv_trinket+moon_cloak.png'}},
    "moon_ring":             {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'stress': 10},
                              "thumb": {'inv_trinket+moon_ring.png'}},
    "quick_draw_charm":      {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'spd': -3},
                              "thumb": {'inv_trinket+quick_draw_charm.png'}},
    "recovery_charm":        {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": None,
                              "thumb": {'inv_trinket+recovery_charm.png'}},
    "snipers_ring":          {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'spd': -2},
                              "thumb": {'inv_trinket+snipers_ring.png'}},
    "solar_crown":           {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": None,
                              "thumb": {'inv_trinket+solar_crown.png'}},
    "sun_cloak":             {"type": 'trinket', "value": 2250, "rating": 5, "keep": 1, "neg": {'stress': 10},
                              "pos": {'dodge': 10, 'prot': 5}, "req": {'sun': 75},
                              "thumb": {'inv_trinket+sun_cloak.png'}},
    "sun_ring":              {"type": 'trinket', "value": 2250, "rating": 6, "keep": 2, "neg": {'stress': 10},
                              "pos": {'dmg': 10, 'acc': 5}, "req": {'sun': 75}, "thumb": {'inv_trinket+sun_ring.png'}},
    "unholy_slayers_ring":   {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "neg": {'dodge': -8},
                              "thumb": {'inv_trinket+unholy_slayers_ring.png'}},

    # Rare (Hero) Trinkets
    "padlock_4":           {"type": 'trinket', "value": 2250, "rating": 7, "keep": 1, "hero_class": 'abomination',
                            "neg": {'hp': -10}, "pos": {'dmg': 10, 'spd': 3},
                            "thumb": {'inv_trinket+padlock_4.png'}},  # lock_of_fury
    "antiq_4":             {"type": 'trinket', "value": 2250, "rating": 5, "keep": 1, "hero_class": 'antiquarian',
                            "pos": {'spd': 4}, "thumb": {'inv_trinket+antiq_4.png'}},  # fleet_florin
    "bulls_eye_bandana":   {"type": 'trinket', "value": 2250, "rating": 6, "keep": 1, "hero_class": 'arbalest',
                            "neg": {'dodge': -4}, "pos": {'acc': 8, 'crit': 5},
                            "thumb": {'inv_trinket+bulls_eye_bandana.png'}},
    "hunters_talons":      {"type": 'trinket', "value": 2250, "rating": 5, "keep": 1, "hero_class": 'bounty_hunter',
                            "pos": {'crit': 6, 'acc': 10}, "thumb": {'inv_trinket+hunters_talon.png'}},
    "commanders_order":    {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "hero_class": 'crusader',
                            "neg": {'dmg': -10}, "thumb": {'inv_trinket+commanders_orders.png'}},
    "flag_2":              {"type": 'trinket', "value": 2250, "rating": 6, "keep": 1, "hero_class": 'flagellant',
                            "pos": {'hp': 10}, "thumb": {'inv_trinket+flag_2.png'}},  # sufferings_collar
    "lucky_talisman":      {"type": 'trinket', "value": 2250, "rating": 5, "keep": 1, "hero_class": 'grave_robber',
                            "neg": {'stress': 10}, "pos": {'dodge': 12, 'ranged_acc': 10},
                            "thumb": {'inv_trinket+lucky_talisman.png'}},
    "heavens_hairpin":     {"type": 'trinket', "value": 2250, "rating": 8, "keep": 2, "hero_class": 'hellion',
                            "pos": {'stress': -25, 'acc': 10}, "req": {'sun': 75},
                            "thumb": {'inv_trinket+heavens_hairpin.png'}},
    "sharpening_sheath":   {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "hero_class": 'highwayman',
                            "neg": {'spd': -1}, "thumb": {'inv_trinket+sharpening_sheath.png'}},
    "protective_collar":   {"type": 'trinket', "value": 2250, "rating": 4, "keep": 1, "hero_class": 'houndmaster',
                            "neg": {'dmg': -15}, "pos": {'dodge': 12}, "thumb": {'inv_trinket+protective_collar.png'}},
    "bright_tambourine":   {"type": 'trinket', "value": 2250, "rating": 10, "keep": 2, "hero_class": 'jester',
                            "pos": {'stress_heal': 20, }, "req": {'sun': 51},
                            "thumb": {'inv_trinket+bright_tambourine.png'}},
    "immunity_mask":       {"type": 'trinket', "value": 2250, "rating": 4, "keep": 1, "hero_class": 'leper',
                            "neg": {'hp': -10}, "thumb": {'inv_trinket+immunity_mask.png'}},
    "rampart_shield":      {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "hero_class": 'man-at-arms',
                            "neg": {'dmg': -15}, "thumb": {'inv_trinket+rampart_shield.png'}},
    "bulls_eye_hat":       {"type": 'trinket', "value": 2250, "rating": 6, "keep": 1, "hero_class": 'musketeer',
                            "neg": {'dodge': -4}, "pos": {'acc': 8, 'crit': 5},
                            "thumb": {'inv_trinket+bulls_eye_hat.png'}},
    "sacrifical_cauldron": {"type": 'trinket', "value": 2250, "rating": 6, "keep": 1, "hero_class": 'occultist',
                            "neg": {'stress': 10}, "pos": {'dmg': 20},
                            "thumb": {'inv_trinket+sacrificial_cauldron.png'}},
    "bloody_herb":         {"type": 'trinket', "value": 2250, "rating": 5, "keep": 1, "hero_class": 'plague_doctor',
                            "thumb": {'inv_trinket+bloody_herb.png'}},
    "sb_4":                {"type": 'trinket', "value": 2250, "rating": 0, "keep": 1, "hero_class": 'shieldbreaker',
                            "thumb": {'inv_trinket+sb_4.png'}},  # fanged_spear_tip
    "profane_scroll":      {"type": 'trinket', "value": 2250, "rating": 0, "keep": 0, "hero_class": 'vestal',
                            "neg": {'stress': 15}, "thumb": {'inv_trinket+profane_scroll.png'}},
    "book_of_holy_healing": {"type": 'trinket', "value": 2250, "rating": 6, "keep": 1, "hero_class": 'vestal',
                             "neg": {'hp': -15}, "pos": {'heal': 25},
                             "thumb": {'inv_trinket+book_of_holy_healing.png'}},  # tome_of_holy_healing

    # Very Rare Trinkets
    "book_of_sanity":    {"type": 'trinket', "value": 3750, "rating": 8, "keep": 2, "pos": {'stress': -20},
                          "thumb": {'inv_trinket+book_of_sanity.png'}},
    "cleansing_crystal": {"type": 'trinket', "value": 3750, "rating": 6, "keep": 1, "neg": None,
                          "thumb": {'inv_trinket+cleansing_crystal.png'}},
    "ethereal_crucifix": {"type": 'trinket', "value": 3750, "rating": 0, "keep": 1, "neg": {'hp': -20},
                          "thumb": {'inv_trinket+ethereal_crucifix.png'}},
    "focus_ring":        {"type": 'trinket', "value": 3750, "rating": 10, "keep": 3, "neg": {'dodge': -8},
                          "pos": {'acc': 10, 'crit': 5}, "thumb": {'inv_trinket+focus_ring.png'}},
    "fortifying_garlic": {"type": 'trinket', "value": 3750, "rating": 6, "keep": 2, "neg": None,
                          "thumb": {'inv_trinket+fortifying_garlic.png'}},
    "heros_ring":        {"type": 'trinket', "value": 3750, "rating": 9, "keep": 2, "pos": {'virtue': 25},
                          "thumb": {'inv_trinket+heros_ring.png'}},
    "legendary_bracer":  {"type": 'trinket', "value": 3750, "rating": 10, "keep": 3, "neg": {'stress': 10, 'spd': -1},
                          "pos": {'dmg': 20}, "thumb": {'inv_trinket+legendary_bracer.png'}},
    "martyrs_seal":      {"type": 'trinket', "value": 3750, "rating": 8, "keep": 2, "neg": None, "pos": {'hp': 15},
                          "thumb": {'inv_trinket+martyrs_seal.png'}},
    "tough_ring":        {"type": 'trinket', "value": 3750, "rating": 7, "keep": 2, "neg": {'stress': 10, 'dmg': -15},
                          "pos": {'prot': 10, 'hp': 15}, "thumb": {'inv_trinket+tough_ring.png'}},

    # Very Rare (Hero) Trinkets
    "padlock_5":           {"type": 'trinket', "value": 3750, "rating": 6, "keep": 1, "hero_class": 'abomination',
                            "thumb": {'inv_trinket+padlock_5.png'}},  # restraining_padlock
    "antiq_5":             {"type": 'trinket', "value": 3750, "rating": 7, "keep": 2, "hero_class": 'antiquarian',
                            "pos": {'heal': 50, 'hp': 15}, "thumb": {'inv_trinket+antiq_5.png'}},  # candle_of_life
    "wrathful_bandana":    {"type": 'trinket', "value": 3750, "rating": 3, "keep": 0, "hero_class": 'arbalest',
                            "neg": {'heal': -50}, "thumb": {'inv_trinket+wrathful_bandana.png'}},
    "wounding_helmet":     {"type": 'trinket', "value": 3750, "rating": 5, "keep": 1, "hero_class": 'bounty_hunter',
                            "neg": {'stun_chance': -20}, "pos": {'melee_dmg': 25},
                            "thumb": {'inv_trinket+wounding_helmet.png'}},
    "holy_orders":         {"type": 'trinket', "value": 3750, "rating": 4, "keep": 0, "hero_class": 'crusader',
                            "thumb": {'inv_trinket+holy_orders.png'}},
    "flag_1":              {"type": 'trinket', "value": 3750, "rating": 0, "keep": 0, "hero_class": 'flagellant',
                            "thumb": {'inv_trinket+flag_1.png'}},  # eternitys_collar
    "raiders_talisman":    {"type": 'trinket', "value": 3750, "rating": 8, "keep": 2, "hero_class": 'grave_robber',
                            "neg": {'hp': -10}, "pos": {'crit': 5, 'trap': 30, 'spd': 2, 'scout': 15},
                            "thumb": {'inv_trinket+raiders_talisman.png'}},
    "hells_hairpin":       {"type": 'trinket', "value": 3750, "rating": 0, "keep": 0, "hero_class": 'hellion',
                            "thumb": {'inv_trinket+hells_hairpin.png'}},
    "poisoning_buckle":    {"type": 'trinket', "value": 3750, "rating": 6, "keep": 1, "hero_class": 'highwayman',
                            "neg": {'melee_dmg': -10}, "pos": {'ranged_dmg': 20, 'ranged_acc': 15},
                            "thumb": {'inv_trinket+poisoning_buckle.png'}},  # gunslingers_buckle
    "spiked_collar":       {"type": 'trinket', "value": 3750, "rating": 6, "keep": 1, "hero_class": 'houndmaster',
                            "neg": {'heal': -50, 'healed': -20}, "pos": {'dmg': 20},
                            "thumb": {'inv_trinket+spiked_collar.png'}},
    "dark_tambourine":     {"type": 'trinket', "value": 3750, "rating": 0, "keep": 0, "hero_class": 'jester',
                            "thumb": {'inv_trinket+dark_tambourine.png'}},
    "berserk_mask":        {"type": 'trinket', "value": 3750, "rating": 6, "keep": 1, "hero_class": 'leper',
                            "neg": {'healed': -33, 'virtue': -10}, "pos": {'crit': 8, 'spd': 3},
                            "thumb": {'inv_trinket+berserk_mask.png'}},
    "guardians_shield":    {"type": 'trinket', "value": 3750, "rating": 0, "keep": 0, "hero_class": 'man-at-arms',
                            "thumb": {'inv_trinket+guardians_shield.png'}},
    "wrathful_hat":        {"type": 'trinket', "value": 3750, "rating": 3, "keep": 0, "hero_class": 'musketeer',
                            "neg": {'heal': -30, 'healed': -30}, "thumb": {'inv_trinket+wrathful_hat.png'}},
    "demons_cauldron":     {"type": 'trinket', "value": 3750, "rating": 3, "keep": 0, "hero_class": 'occultist',
                            "neg": {'stress': 15, 'virtue': -10},
                            "pos": {'stun_chance': 30, 'deb_chance': 40, 'crit': 3},
                            "thumb": {'inv_trinket+demons_cauldron.png'}},
    "blasphemous_vial":    {"type": 'trinket', "value": 3750, "rating": 10, "keep": 2, "hero_class": 'plague_doctor',
                            "neg": {'stress': 25}, "pos": {'ranged_acc': 10, 'stun_chance': 20},
                            "thumb": {'inv_trinket+blasphemous_vial.png'}},
    "sb_5":                {"type": 'trinket', "value": 3750, "rating": 4, "keep": 1, "hero_class": 'shieldbreaker',
                            "neg": {'spd': -2}, "pos": {'hp': 33},
                            "thumb": {'inv_trinket+sb_5.png'}},  # cuirboilli
    "sacred_scroll":       {"type": 'trinket', "value": 3750, "rating": 3, "keep": 0, "hero_class": 'vestal',
                            "neg": {'dmg': -33, 'stun_chance': -10}, "pos": {'stress': -10, 'heal': 33},
                            "thumb": {'inv_trinket+sacred_scroll.png'}},

    # Ancestral Trinkets
    "ancestors_bottle":         {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "neg": {'stress': 10},
                                 "pos": {'hp': 25}, "thumb": {'inv_trinket+ancestors_bottle.png'}},
    "ancestors_candle":         {"type": 'trinket', "value": 7500, "rating": 9, "keep": 1, "neg": {'stress': 10},
                                 "pos": {'dmg': 15,'spd': 2, 'dodge': 5}, "req": {'sun': 50},
                                 "thumb": {'inv_trinket+ancestors_candle.png'}},
    "ancestors_coat":           {"type": 'trinket', "value": 7500, "rating": 6, "keep": 1, "neg": {'stress': 10},
                                 "pos": {'dodge': 15}, "thumb": {'inv_trinket+ancestors_coat.png'}},
    "ancestors_handkerchief":   {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "neg": {'stress': 10},
                                 "thumb": {'inv_trinket+ancestors_handkerchief.png'}},
    "ancestors_lantern":        {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "neg": {'stress': 10},
                                 "thumb": {'inv_trinket+ancestors_lantern.png'}},
    "ancestors_map":           {"type": 'trinket', "value": 7500, "rating": 10, "keep": 1, "neg": {'stress': 10},
                                "pos": {'scout': 25, 'trap': 25}, "thumb": {'inv_trinket+ancestors_map.png'}},
    "ancestors_mustache_cream": {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "neg": {'stress': 10},
                                 "thumb": {'inv_trinket+ancestors_moustache_cream.png'}},
    "ancestors_musket_ball":    {"type": 'trinket', "value": 7500, "rating": 6, "keep": 1, "neg": {'stress': 10},
                                 "pos": {'ranged_dmg': 10, 'ranged_crit': 8},
                                 "thumb": {'inv_trinket+ancestors_musket_ball.png'}},
    "ancestors_pen":            {"type": 'trinket', "value": 7500, "rating": 7, "keep": 1, "neg": {'stress': 10},
                                 "pos": {'melee_dmg': 10, 'melee_crit': 8}, "thumb": {'inv_trinket+ancestors_pen.png'}},
    "ancestors_pistol":         {"type": 'trinket', "value": 7500, "rating": 8, "keep": 1, "neg": {'stress': 10},
                                 "pos": {'spd': 3, 'ranged_acc': 15}, "thumb": {'inv_trinket+ancestors_pistol.png'}},
    "ancestors_portrait":       {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "neg": {'stress': 10},
                                 "thumb": {'inv_trinket+ancestors_portrait.png'}},
    "ancestors_scroll":        {"type": 'trinket', "value": 7500, "rating": 10, "keep": 1, "neg": {'stress': 10},
                                "pos": {'heal': 25,'stress_heal': 25}, "thumb": {'inv_trinket+ancestors_scroll.png'}},
    "ancestors_signet_ring":    {"type": 'trinket', "value": 7500, "rating": 9, "keep": 1, "neg": {'stress': 10},
                                 "pos": {'acc': 10, 'prot': 10}, "thumb": {'inv_trinket+ancestors_signet_ring.png'}},
    "ancestors_tentacle_idol":  {"type": 'trinket', "value": 7500, "rating": 8, "keep": 1, "pos": {'virtue': 20},
                                 "thumb": {'inv_trinket+ancestors_tentacle_idol.png'}},

    # Crimson Court Trinkets
    "cc_crimson_tincture": {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+cc_crimson_tincture.png'}},  # ancestors_vintage
    "cc_coven_signet":     {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+cc_coven_signet.png'}},  # coven_signet
    "dazzling_mirror":   {"type": 'trinket', "value": 7500, "rating": 9, "keep": 1,
                          "pos": {'spd': 4,'stun_chance': 20}, "req": {'enemy': 'bloodsucker'},
                          "thumb": {'inv_trinket+cc_dazzling_mirror.png'}},
    "mantra_of_fasting": {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1,
                          "thumb": {'inv_trinket+cc_mantra_of_fasting.png'}},
    "mercurial_salve":   {"type": 'trinket', "value": 7500, "rating": 8, "keep": 1,
                          "pos": {'dmg': 25}, "req": {'enemy': 'bloodsucker'},
                          "thumb": {'inv_trinket+cc_quicksilver_salve.png'}},
    "pagan_talisman":    {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1,
                          "thumb": {'inv_trinket+cc_pagan_talisman.png'}},
    "rat_carcass":       {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1,
                          "thumb": {'inv_trinket+cc_rat_carcass.png'}},
    "sanguine_snuff":    {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1,
                          "thumb": {'inv_trinket+cc_crystal_snifter.png'}},
    "sculptors_tools":   {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1,
                          "thumb": {'inv_trinket+cc_sculptors_tools.png'}},

    # Crimson Court (Hero) Trinkets
    "shameful_shroud":         {"type": 'trinket', "value": 7500, "rating": 6, "keep": 1, "hero_class": 'abomination',
                                "pos": {'stress': -15,'dodge': 10}, "thumb": {''}},
    "osmond_chains":           {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'abomination',
                                "thumb": {''}},
    "the_masters_essence":     {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'antiquarian',
                                "thumb": {''}},
    "two_of_three":            {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'antiquarian',
                                "thumb": {''}},
    "childhood_treasure":      {"type": 'trinket', "value": 7500, "rating": 4, "keep": 1, "hero_class": 'arbalest',
                                "pos": {'stress': -15,'heal': 30}, "thumb": {''}},
    "bedtime_story":           {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'arbalest',
                                "thumb": {''}},
    "crime_lords_molars":      {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'bounty_hunter',
                                "neg": {'dodge': -10}, "thumb": {''}},
    "vengeful_kill_list":     {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'bounty_hunter',
                               "thumb": {''}},
    "glittering_spaulders":    {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'crusader',
                                "thumb": {''}},
    "signed_conscription":     {"type": 'trinket', "value": 7500, "rating": 8, "keep": 1, "hero_class": 'crusader',
                                "pos": {'stress_heal': 20, 'heal': 20}, "thumb": {''}},
    "chipped_tooth":           {"type": 'trinket', "value": 7500, "rating": 7, "keep": 1, "hero_class": 'flagellant',
                                "pos": {'hp': 20}, "thumb": {''}},
    "shard_of_glass":          {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'flagellant',
                                "thumb": {''}},
    "absinthe":                {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'grave_robber',
                                "neg": {'hp: -10'}, "thumb": {''}},
    "sharpened_letter_opener": {"type": 'trinket', "value": 7500, "rating": 7, "keep": 1, "hero_class": 'grave_robber',
                                "pos": {'melee_dmg': 25,'melee_acc': 10, 'dodge': 5}, "thumb": {''}},
    "lioness_warpaint":        {"type": 'trinket', "value": 7500, "rating": 4, "keep": 1, "hero_class": 'hellion',
                                "neg": {'stress': 10}, "thumb": {''}},
    "mark_of_the_outcast":     {"type": 'trinket', "value": 7500, "rating": 4, "keep": 1, "hero_class": 'hellion',
                                "neg": {'healed': -15}, "pos": {'spd': 2}, "thumb": {''}},
    "bloodied_neckerchief":    {"type": 'trinket', "value": 7500, "rating": 8, "keep": 1, "hero_class": 'highwayman',
                                "pos": {'spd': 2,'dodge': 10}, "thumb": {''}},
    "shameful_locket":         {"type": 'trinket', "value": 7500, "rating": 9, "keep": 1, "hero_class": 'highwayman',
                                "neg": {'stress': 15}, "pos": {'acc': 10, 'crit': 5}, "thumb": {''}},
    "evidence_of_corruption":  {"type": 'trinket', "value": 7500, "rating": 8, "keep": 1, "hero_class": 'houndmaster',
                                "neg": {'stress': 10}, "pos": {'scout': 25}, "thumb": {''}},
    "battered_lawmans_badge":  {"type": 'trinket', "value": 7500, "rating": 3, "keep": 1, "hero_class": 'houndmaster',
                                "pos": {'ranged_acc': 15, 'heal': 25}, "thumb": {''}},
    "tyrants_tasting_cup":     {"type": 'trinket', "value": 7500, "rating": 8, "keep": 1, "hero_class": 'jester',
                                "neg": {'stress': 25}, "pos": {'stress_heal': 33}, "thumb": {''}},
    "tyrants_fingerbone":      {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'jester',
                                "thumb": {''}},
    "last_will_and_testament": {"type": 'trinket', "value": 7500, "rating": 5, "keep": 1, "hero_class": 'leper',
                                "pos": {'prot': 15, 'hp': 15}, "thumb": {''}},
    "tin_flute":               {"type": 'trinket', "value": 7500, "rating": 0, "keep": 5, "hero_class": 'leper',
                                "pos": {'stress': -20}, "thumb": {''}},
    "old_unit_standard":       {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'man-at-arms',
                                "neg": {'stress': 10}, "thumb": {''}},
    "toy_soldier":             {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'man-at-arms',
                                "thumb": {''}},
    "second_place_trophy":     {"type": 'trinket', "value": 7500, "rating": 3, "keep": 1, "hero_class": 'musketeer',
                                "thumb": {''}},
    "silver_musket_ball":      {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'musketeer',
                                "thumb": {''}},
    "blood_pact":              {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'occultist',
                                "neg": {'bld_chance': -25, 'hp': -10}, "thumb": {''}},
    "vial_of_sand":            {"type": 'trinket', "value": 7500, "rating": 6, "keep": 1, "hero_class": 'occultist',
                                "pos": {'stun_chance': 20, 'deb_chance': 20}, "thumb": {''}},
    "subject_#40_notes":       {"type": 'trinket', "value": 7500, "rating": 4, "keep": 1, "hero_class": 'plague_doctor',
                                "pos": {'hp': 25}, "thumb": {''}},
    "dissection_kit":         {"type": 'trinket', "value": 7500, "rating": 3, "keep": 1, "hero_class": 'plague_doctor',
                               "thumb": {''}},
    "obsidian_dagger":        {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'shieldbreaker',
                               "thumb": {'inv_trinket+sb_set_1.png'}},
    "severed_hand":           {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'shieldbreaker',
                               "thumb": {'inv_trinket+sb_set_2.png'}},
    "atonement_beads":        {"type": 'trinket', "value": 7500, "rating": 0, "keep": 1, "hero_class": 'vestal',
                               "neg": {'virtue': -15}, "thumb": {''}},
    "salacious_diary":        {"type": 'trinket', "value": 7500, "rating": 10, "keep": 1, "hero_class": 'vestal',
                               "pos": {'heal': 25}, "thumb": {''}},

    # Unique Monster Trinkets
    "madman_1":           {"type": 'trinket', "value": 2250, "rating": 8, "keep": 1, "pos": {'stress': -25},
                           "thumb": {'inv_trinket+madman_1.png'}},  # aria_box
    "madman_3":          {"type": 'trinket', "value": 2250, "rating": 10, "keep": 1, "neg": {'stress': 10},
                          "pos": {'dmg': 15, 'spd': 2}, "thumb": {'inv_trinket+madman_3.png'}},  # crescendo_box
    "madman_2":           {"type": 'trinket', "value": 2250, "rating": 7, "keep": 1, "neg": {'acc': -2},
                           "pos": {'hp': 15,'dodge': 8},
                           "thumb": {'inv_trinket+music_box.png', 'inv_trinket+madman_2.png'}},  # overture_box
    "collector_2":        {"type": 'trinket', "value": 2250, "rating": 0, "keep": 1, "neg": {'stress': 20},
                           "thumb": {'inv_trinket+collector_2.png'}},  # barristans_head
    "collector_1":       {"type": 'trinket', "value": 2250, "rating": 10, "keep": 1, "neg": {'stress': 20, 'hp': -10},
                          "pos": {'dmg': 25}, "thumb": {'inv_trinket+collector_1.png'}},  # dismas_head
    "collector_3":       {"type": 'trinket', "value": 2250, "rating": 10, "keep": 1, "neg": {'stress': 20},
                          "pos": {'heal': 30}, "thumb": {'inv_trinket+collector_3.png'}},  # junias_head
    "tempting_goblet":    {"type": 'trinket', "value": 2250, "rating": 8, "keep": 1,
                           "neg": {'stress': 25, 'virtue': -10}, "pos": {'spd': 3,'hp': 20,'dodge': 8},
                           "thumb": {'inv_trinket+tempting_goblet.png'}},
    "crow_talon":         {"type": 'trinket', "value": 2250, "rating": 0, "keep": 1, "neg": {'stress': 15},
                           "thumb": {'inv_trinket+crow_talon.png'}},  # callous_talon
    "crow_eye":           {"type": 'trinket', "value": 2250, "rating": 5, "keep": 1, "neg": {'stress': 15},
                           "pos": {'acc': 10}, "thumb": {'inv_trinket+crow_eye.png'}},  # distended_crowseye
    "crow_tailfeather":   {"type": 'trinket', "value": 2250, "rating": 6, "keep": 1, "neg": {'stress': 15},
                           "pos": {'spd': 4}, "thumb": {'inv_trinket+crow_tailfeather.png'}},  # molted_tailfeather
    "crow_wingfeather":   {"type": 'trinket', "value": 2250, "rating": 5, "keep": 1, "neg": {'stress': 15},
                           "pos": {'dodge': 10}, "thumb": {'inv_trinket+crow_wingfeather.png'}},  # molted_wingfeather

    # Darkest Dungeon Trinkets
    "talisman_of_the_flame": {"type": 'trinket', "use": {'quest'}, "rating": 0, "keep": 3,
                              "thumb": {'inv_trinket_unlock+dd_trinket.png', 'inv_trinket+dd_trinket.png'}},

    # Trophies
    "boss_necromancer":    {"type": 'trinket', "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+boss_necromancer.png'}},  # necromancers_collar
    "boss_prophet":        {"type": 'trinket', "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+boss_prophet.png'}},  # prophets_eye
    "boss_hag":            {"type": 'trinket', "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+boss_hag.png'}},  # hags_ladle
    "boss_cannon":         {"type": 'trinket', "rating": 8, "keep": 1,
                            "pos": {'ranged_dmg': 10, 'ranged_crit': 6,'spd': 2},
                            "thumb": {'inv_trinket+boss_cannon.png'}},  # fusemans_matchstick
    "boss_wilbur":         {"type": 'trinket', "rating": 7, "keep": 1, "pos": {'dodge': 10},
                            "thumb": {'inv_trinket+boss_wilbur.png'}},  # wilburs_flag
    "boss_flesh":          {"type": 'trinket', "rating": 7, "keep": 1, "pos": {'hp': 15},
                            "thumb": {'inv_trinket+boss_flesh.png'}},  # fleshs_heart
    "boss_siren":          {"type": 'trinket', "rating": 7, "keep": 1, "pos": {'stress': -20},
                            "thumb": {'inv_trinket+boss_siren.png'}},  # sirens_conch
    "boss_crew":           {"type": 'trinket', "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+boss_crew.png'}},  # crews_bell
    "boss_tassle":         {"type": 'trinket', "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+boss_tassle.png'}},  # vvulfs_tassle
    "cc_boss_baron":       {"type": 'trinket', "rating": 5, "keep": 1, "pos": {'spd': 4}, "req": {'crimson_curse'},
                            "thumb": {'inv_trinket+cc_boss_baron.png'}},  # barons_lash
    "cc_boss_viscount":    {"type": 'trinket', "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+cc_boss_viscount.png'}},  # viscounts_spices
    "cc_boss_countess":    {"type": 'trinket', "rating": 0, "keep": 1,
                            "thumb": {'inv_trinket+cc_boss_countess.png'}},  # countess_fan

    # Crystalline Trinkets
    "lens_of_the_comet":   {"type": 'trinket', "shard_value": 25, "rating": 0, "keep": 1, "hero_class": None,
                            "neg": {'virtue': -20}, "thumb": {''}},
    "petrified_skull":     {"type": 'trinket', "shard_value": 25, "rating": 0, "keep": 1, "hero_class": 'occultist',
                            "neg": {'healed': -20}, "thumb": {''}},
    "broken_key":          {"type": 'trinket', "shard_value": 30, "rating": 5, "keep": 1, "hero_class": 'abomination',
                            "neg": {'stress': 10}, "pos": {'acc': 15,'stun_chance': 35}, "thumb": {''}},
    "smoking_skull":       {"type": 'trinket', "shard_value": 45, "rating": 0, "keep": 1, "hero_class": 'antiquarian',
                            "neg": {'acc': -15}, "thumb": {''}},
    "ashen_distillation":  {"type": 'trinket', "shard_value": 45, "rating": 6, "keep": 1, "hero_class": 'plague_doctor',
                            "pos": {'dodge': 20}, "thumb": {''}},
    "dirge_for_the_devoured": {"type": 'trinket', "shard_value": 60, "rating": 8, "keep": 1, "hero_class": 'jester',
                               "neg": {'stress': 10}, "pos": {'stress_heal': 25}, "thumb": {''}},
    "acidic_husk_ichor":   {"type": 'trinket', "shard_value": 65, "rating": 0, "keep": 1, "hero_class": 'flagellant',
                            "neg": {'hp': -25}, "thumb": {''}},
    "spectral_speartip":   {"type": 'trinket', "shard_value": 65, "rating": 7, "keep": 1, "hero_class": 'shieldbreaker',
                            "neg": {'rand_target': 5}, "pos": {'dmg': 15, 'hp': 15}, "thumb": {''}},
    "crystal_pendant":     {"type": 'trinket', "shard_value": 65, "rating": 0, "keep": 1, "hero_class": None,
                            "neg": {'stress': 15}, "thumb": {''}},
    "heretical_passage":   {"type": 'trinket', "shard_value": 70, "rating": 0, "keep": 1, "hero_class": 'vestal',
                            "neg": {'stress': 10}, "thumb": {''}},
    "huskfang_whistle":    {"type": 'trinket', "shard_value": 70, "rating": 0, "keep": 1, "hero_class": 'houndmaster',
                            "neg": {'dodge': -10}, "thumb": {''}},
    "mask_of_the_timeless": {"type": 'trinket', "shard_value": 75, "rating": 6, "keep": 1, "hero_class": 'bounty_hunter',
                             "neg": {'stress': 5}, "pos": {'spd': 2,'dodge': 15}, "thumb": {''}},
    "mirror_shield":       {"type": 'trinket', "shard_value": 75, "rating": 6, "keep": 1, "hero_class": 'man-at-arms',
                            "pos": {'dodge': 10}, "thumb": {''}},
    "topshelf_tonic":      {"type": 'trinket', "shard_value": 80, "rating": 0, "keep": 1, "hero_class": 'grave_robber',
                            "thumb": {''}},
    "petrified_amulet":    {"type": 'trinket', "shard_value": 80, "rating": 0, "keep": 1, "hero_class": 'leper',
                            "thumb": {''}},
    "crystalline_gunpowder": {"type": 'trinket', "shard_value": 90, "rating": 10, "keep": 1, "hero_class": 'highwayman',
                              "pos": {'dmg': 20,'speed': 3}, "thumb": {''}},
    "cluster_pendant":       {"type": 'trinket', "shard_value": 100, "rating": 0, "keep": 1, "hero_class": None,
                              "neg": {'stress': 15}, "thumb": {''}},
    "thirsting_blade":       {"type": 'trinket', "shard_value": 120, "rating": 9, "keep": 1, "hero_class": 'hellion',
                              "pos": {'acc': 15, 'spd': 2}, "thumb": {''}},
    "icosahedric_musket_balls": {"type": 'trinket', "shard_value": 150, "rating": 0, "keep": 1, "hero_class": 'musketeer',
                                 "neg": {'rand_target': 20}, "pos": {'dmg': 20}, "thumb": {''}},
    "keening_bolts":          {"type": 'trinket', "shard_value": 170, "rating": 0, "keep": 1, "hero_class": 'arbalest',
                               "thumb": {''}},
    "coat_of_many_colors":    {"type": 'trinket', "shard_value": 180, "rating": 0, "keep": 1, "hero_class": None,
                               "thumb": {''}},
    "millers_pipe":           {"type": 'trinket', "shard_value": 180, "rating": 0, "keep": 1, "hero_class": None,
                               "thumb": {''}},
    "non-euclidean_hilt":     {"type": 'trinket', "shard_value": 200, "rating": 0, "keep": 1, "hero_class": 'crusader',
                               "neg": {'rand_target': 5}, "pos": {'health': 15, 'stun_chance': 25},
                               "req": {'item': 'holy_water'}, "thumb": {''}},
    "mildreds_locket":        {"type": 'trinket', "shard_value": None, "rating": 10, "keep": 1, "pos": {'spd': 3},
                               "thumb": {''}},
    "things_mesmerizing_eye": {"type": 'trinket', "shard_value": None, "rating": 0, "keep": 1, "thumb": {''}},
    "crystalline_fang":       {"type": 'trinket', "shard_value": None, "rating": 5, "keep": 1, "thumb": {''}},
    "phase_shifting_hide":    {"type": 'trinket', "shard_value": None, "rating": 3, "keep": 1, "pos": {'stress': 15},
                               "thumb": {''}},
    "prismatic_heart_crystal": {"type": 'trinket', "shard_value": None, "rating": 0, "keep": 1, "thumb": {''}},
}
