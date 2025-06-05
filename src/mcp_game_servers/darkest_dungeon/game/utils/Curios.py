import math


def provision_to_use(curio_prop, areas, raid_info, party, inventory, dungeon_path):
    curio = Curios[curio_prop]
    provision, item = None, None
    if not curio['skip'] and curio['provision'] is not None:
        needed_provisions = determine_provisions_needed(areas, raid_info, inventory, party, dungeon_path)
        for i, reward in enumerate(curio['reward']):
            # quest
            if reward == 'quest':
                provision = None if curio['provision'] is None else curio['provision'][i]
                break
            # really need stress heal (use provision if required)
            if reward == 'stress_heal' and any(hero.stress >= 70 for hero in party):
                if curio['name'] == 'ConfessionBooth':
                    total = inventory.provision_totals[curio['provision'][i]]
                    if i < len(curio['provision']) and total > 0:
                        provision = curio['provision'][i]
                        break
                elif curio['name'] != 'ConfessionBooth':
                    if curio['provision'] is None:
                        break
                    if not curio['provision_required']:
                        break
                    total = inventory.provision_totals[curio['provision'][i]]
                    if i < len(curio['provision']) and total > 0:
                        provision = curio['provision'][i]
                        break
            # purge negative quirk
            if reward == 'purge_negative_quirk':
                negative_quirk = False
                for hero in party:
                    if any(quirk['rating'] < 0 for quirk in hero.quirks):
                        negative_quirk = True
                if negative_quirk and i < len(curio['provision']) \
                        and inventory.provision_totals[curio['provision'][i]] > 0:
                    provision = curio['provision'][i]
                    break
            # heal or stress heal (sometimes doesn't require a provision)
            if (reward == 'heal' and any(hero.percentHp <= 20 for hero in party)) \
                    or (reward == 'stress_heal' and any(hero.stress >= 30 for hero in party)
                        and curio['name'] != 'ConfessionBooth'):
                if curio['provision'] is None:
                    break
                total = inventory.provision_totals[curio['provision'][i]]
                if i < len(curio['provision']) and total > 0 and needed_provisions[curio['provision'][i]] < total:
                    provision = curio['provision'][i]
                    break
                if not curio['provision_required']:
                    break
            # treasure (sometimes doesn't require a provision)
            if reward == 'treasure':
                if curio['provision'] is None or i >= len(curio['provision']):
                    break
                p = curio['provision'][i]
                if i < len(curio['provision']) and inventory.provision_totals[p] > 0 and p != 'shovel':
                    provision = p
                    break
                if i < len(curio['provision']) and inventory.provision_totals[p] > 0 and p == 'shovel':
                    unscouted_rooms, scouted_obstacles = 0, 0
                    for name, area in areas.items():
                        if name.startswith('roo') and area['knowledge'] == 1:
                            unscouted_rooms += 1
                        elif area['knowledge'] > 1:
                            scouted_obstacles = sum(each_tile['content'] == 4 for each_tile in area['tiles'].values())
                    needed_shovels = math.ceil(unscouted_rooms / 3) + scouted_obstacles
                    if i < len(curio['provision']) and inventory.provision_totals[p] > needed_shovels:
                        provision = p
                        break
                if not curio['provision_required']:
                    break
            # damage buff or defense buff (sometimes doesn't require a provision)
            if reward == 'dmg_buff' or reward == 'def_buff':
                if curio['provision'] is None:
                    break
                total = inventory.provision_totals[curio['provision'][i]]
                if i < len(curio['provision']) and total > inventory.starting_provisions[curio['provision'][i]]:
                    provision = curio['provision'][i]
                    break
                if not curio['provision_required']:
                    break
            # future - max light ??? (only useful if low on torches)
    if provision is not None:
        items = [i for i in inventory.items if i.name == provision]
        items.sort(key=lambda k: (k.quantity, k.item_slot))
        item = items[0]
    elif provision is None and curio['provision_required']:
        print(f"Skipping ({curio['name']}). Need to save provisions or not enough!")
    return provision, item


def determine_provisions_needed(areas, raid_info, inventory, party, dungeon_path):
    dungeon = raid_info['raid_instance']['dungeon']
    difficulty = raid_info['raid_instance']['difficulty']
    rooms = len([name for name, area in areas.items() if name.startswith('roo')])
    # dungeon_path, _ = get_dungeon_path(raid_info, static_areas, location)
    rooms_left = len([name for name, area in areas.items() if name.startswith('roo') and area['knowledge'] != 3])
    unscouted_rooms = len([name for name, area in areas.items() if name.startswith('roo') and area['knowledge'] == 1])
    scouted_curios = []
    needed_provisions = {'torch': 0, 'food': 0, 'antivenom': 0, 'bandage': 0, 'holy_water': 0, 'skeleton_key': 0,
                         'shovel': 0, 'medicinal_herbs': 0}

    # add torches and food for number of rooms left (future - come up with a better way to calculate)
    needed_provisions['torch'] += math.ceil(inventory.starting_provisions['torch'] * rooms_left / rooms)
    # can't use number of rooms left for food because of still need when backtracking, instead use dungeon_path + 1
    needed_provisions['food'] += math.floor((len(dungeon_path) + 3) / 3) * 4
    firewood = sum(item.name == 'firewood' for item in inventory.items)
    if firewood > 0:
        if any(ally.stress >= 30 for ally in party) or sum(ally.stress >= 20 for ally in party) >= 2:
            needed_provisions['food'] += 8
        elif any(ally.percentHp <= 15 for ally in party) or sum(ally.percentHp <= 30 for ally in party) >= 2:
            needed_provisions['food'] += 4
        else:
            needed_provisions['food'] += 2
        if firewood > 1:
            needed_provisions['food'] += 4
    if rooms_left == 0 or inventory.provision_totals['food'] <= 4:  # drop firewood if not enough food to use it
        for item in inventory.items:
            if item.name == 'firewood':
                item.value = 0
        needed_provisions['food'] = 0

    # estimate the provisions needed for unscouted rooms
    if dungeon == 'crypts':  # ruins
        needed_provisions['shovel'] += math.ceil(unscouted_rooms / 3)
        needed_provisions['skeleton_key'] += math.ceil(unscouted_rooms / 3)
    elif dungeon == 'warrens':
        needed_provisions['shovel'] += math.ceil(unscouted_rooms / 3)
        needed_provisions['skeleton_key'] += math.ceil(unscouted_rooms / 3)
    elif dungeon == 'weald':
        needed_provisions['shovel'] += math.ceil(unscouted_rooms / 3)
        needed_provisions['skeleton_key'] += math.ceil(unscouted_rooms / 3)
    elif dungeon == 'cove':
        needed_provisions['shovel'] += math.ceil(unscouted_rooms / 3)
        needed_provisions['skeleton_key'] += math.ceil(unscouted_rooms / 3)
        needed_provisions['medicinal_herbs'] += math.ceil(unscouted_rooms / 3)
        if difficulty > 1:
            # keep bandages if difficulty level >1 and more than 2 rooms left
            needed_provisions['bandage'] += math.ceil(unscouted_rooms / 3)

    # calculate the provisions needed for scouted rooms
    for area in areas.values():
        if area['knowledge'] > 1:
            for each_tile in area['tiles'].values():
                if each_tile['curio_prop'] != 0 and each_tile['content'] != 0:  # curio
                    scouted_curios.append(each_tile['curio_prop'])
                elif each_tile['content'] == 4:  # obstacle
                    needed_provisions['shovel'] += 1

    # first - add easy ones that only require one specific provision
    for curio in scouted_curios:
        if not Curios[curio]['skip'] and Curios[curio]['provision'] is not None \
                and len(Curios[curio]['provision']) == 1:
            # future - check and make sure party needs a heal or stress heal
            # future - add keys for secret rooms if it doesn't already
            if Curios[curio]['reward'][0] == 'treasure' \
                    or (Curios[curio]['reward'][0] == 'purge_negative_quirk'
                        and any(any(quirk['rating'] < 0 for quirk in ally.quirks) for ally in party)):
                provision = Curios[curio]['provision'][0]
                needed_provisions[provision] += 1

    # second - for ones that can take more than one kind of provision, decide which one
    for curio in scouted_curios:
        if not Curios[curio]['skip'] and Curios[curio]['provision'] is not None \
                and Curios[curio]['provision_required'] and len(Curios[curio]['provision']) == 2:
            # LockedSarcophagus, LockedDisplayCabinet, or LeftLuggage
            if Curios[curio]['reward'][0] == 'treasure' and Curios[curio]['reward'][1] == 'treasure':
                if inventory.provision_totals['skeleton_key'] <= needed_provisions['skeleton_key']:
                    provision2 = Curios[curio]['provision'][1]
                    needed_provisions[provision2] += 1
                else:
                    needed_provisions['skeleton_key'] += 1
            elif Curios[curio]['name'] == 'WineCrate':
                pass
            elif Curios[curio]['name'] == 'AlchemyTable':
                needed_provisions['medicinal_herbs'] += 1
    return needed_provisions


Curios = {
    # Shared
    798408319: {'name': 'Crate',          "reward": ['treasure'], "provision": None, "provision_required": False,
                                          "skip": False},
    812819981: {'name': 'DiscardedPack',  "reward": ['treasure', 'scout'], "provision": None,
                                          "provision_required": False, "skip": False},
    2068305038: {'name': 'EldritchAltar', "reward": ['purge_negative_quirk'], "provision": ['holy_water'],
                                          "provision_required": True, "skip": False},
    283272093: {'name': 'HeirloomChest',  "reward": ['treasure'], "provision": ['skeleton_key'],
                                          "provision_required": False, "skip": False},
    17398682: {'name': 'Sack',            "reward": ['treasure'], "provision": None, "provision_required": False,
                                          "skip": False},
    1645838743: {'name': 'Sconce',        "reward": ['treasure'], "provision": None, "provision_required": False,
                                          "skip": False},
    1044552280: {'name': 'ShamblerAltar', "reward": ['fight_shambler'], "provision": ['torch'],
                                          "provision_required": True, "skip": True},
    -1950477141: {'name': 'StackOfBooks',  "reward": None, "provision": ['torch'], "provision_required": False,
                                           "skip": True},
    -1086187210: {'name': 'UnlockedStrongbox', "reward": ['treasure'], "provision": None, "provision_required": False,
                                               "skip": False},
    1140678991:  {'name': 'LockedStrongbox',   "reward": ['treasure'], "provision": ['skeleton_key'],
                                               "provision_required": False, "skip": False},
    -731135492:  {'name': 'SecretStash',   "reward": ['treasure'], "provision": ['skeleton_key'],
                                           "provision_required": False, "skip": False},

    # Tutorial
    -2122369512: {'name': 'TutorialKey',       "reward": ['treasure'], "provision": None, "provision_required": False,
                                               "skip": False},
    -817151165: {'name': 'TutorialFood',       "reward": ['treasure'], "provision": None, "provision_required": False,
                                               "skip": False},
    -816853549: {'name': 'TutorialHoly',       "reward": ['treasure'], "provision": None, "provision_required": False,
                                               "skip": False},
    -778689652: {'name': 'TutorialShovel',     "reward": ['treasure'], "provision": None, "provision_required": False,
                                               "skip": False},
    824803909: {'name': 'TutorialTent',        "reward": ['treasure'], "provision": None, "provision_required": False,
                                               "skip": False},
    908094902: {'name': 'BanditsTrappedChest', "reward": ['treasure'], "provision": ['skeleton_key'],
                                               "provision_required": True, "skip": False},

    # Ruins
    217369390: {'name': 'AlchemyTable', "reward": ['treasure', 'max_light'], "provision": ['medicinal_herbs', 'torch'],
                                        "provision_required": False, "skip": False},
    2063140855: {'name': 'AltarOfLight', "reward": ['dmg_buff'], "provision": ['holy_water'],
                                         "provision_required": False, "skip": False},
    1617409501:  {'name': 'Bookshelf',   "reward": None, "provision": None, "provision_required": False, "skip": True},
    -1654251310: {'name': 'ConfessionBooth', "reward": ['stress_heal', 'purge_negative_quirk', 'treasure'],
                                             "provision": ['holy_water'], "provision_required": False, "skip": False},
    1266967170: {'name': 'DecorativeUrn',    "reward": ['treasure'], "provision": ['holy_water'],
                                             "provision_required": True, "skip": False},
    932141079: {'name': 'HolyFountain',     "reward": ['stress_heal', 'heal', 'treasure'], "provision": ['holy_water'],
                                            "provision_required": False, "skip": False},
    -415006183: {'name': 'IronMaiden',           "reward": ['treasure'], "provision": ['medicinal_herbs'],
                                                 "provision_required": True, "skip": False},
    -1668329672: {'name': 'LockedDisplayCabinet', "reward": ['treasure', 'treasure'],
                                                  "provision": ['skeleton_key', 'shovel'],
                                                  "provision_required": True, "skip": False},
    1855416821: {'name': 'LockedSarcophagus',    "reward": ['treasure', 'treasure'],
                                                 "provision": ['skeleton_key', 'shovel'],
                                                 "provision_required": True, "skip": False},
    -1644485216: {'name': 'Sarcophagus',         "reward": ['treasure'], "provision": None, "provision_required": False,
                                                 "skip": False},
    2120292233: {'name': 'SuitOfArmor',          "reward": ['def_buff'], "provision": None, "provision_required": False,
                                                 "skip": False},

    # Warrens
    -1083492030: {'name': 'BoneAltar',         "reward": ['dmg_buff'], "provision": None, "provision_required": False,
                                               "skip": False},
    841533193:  {'name': 'DinnerCart',           "reward": ['treasure'], "provision": ['medicinal_herbs'],
                                                 "provision_required": True, "skip": False},
    1551004363: {'name': 'MakeshiftDiningTable', "reward": ['treasure'], "provision": ['medicinal_herbs'],
                                                 "provision_required": True, "skip": False},
    -2110570969: {'name': 'MoonshineBarrel',     "reward": ['dmg_buff'], "provision": ['medicinal_herbs'],
                                                 "provision_required": True, "skip": False},
    -386842210:  {'name': 'OccultScrawlings', "reward": None, "provision": ['holy_water'],
                                              "provision_required": False, "skip": True},
    -199372804:  {'name': 'PileOfBones',      "reward": ['treasure'], "provision": ['holy_water'],
                                              "provision_required": True, "skip": False},
    749184735:   {'name': 'PileOfScrolls',    "reward": ['purge_negative_quirk'], "provision": ['torch'],
                                              "provision_required": True, "skip": False},
    2102274661:  {'name': 'RackOfBlades',     "reward": ['treasure'], "provision": ['bandage'],
                                              "provision_required": False, "skip": False},
    723144546:  {'name': 'SacrificialStone',  "reward": ['purge_negative_quirk'], "provision": None,
                                              "provision_required": False, "skip": True},

    # Weald
    1467581002: {'name': 'AncientCoffin',    "reward": ['treasure'], "provision": None, "provision_required": False,
                                             "skip": False},
    -1147263018: {'name': 'BeastCarcass',    "reward": ['treasure'], "provision": ['medicinal_herbs'],
                                             "provision_required": True, "skip": False},
    -2101263498: {'name': 'EerieSpiderwed',  "reward": ['treasure'], "provision": ['bandage'],
                                             "provision_required": True, "skip": False},
    1511313553: {'name': 'LeftLuggage',      "reward": ['treasure', 'treasure'],
                                             "provision": ['skeleton_key', 'antivenom'],
                                             "provision_required": False, "skip": False},
    1498577691: {'name': 'MummifiedRemains', "reward": ['treasure'], "provision": ['bandage'],
                                             "provision_required": False, "skip": False},
    -1179299146: {'name': 'OldTree',         "reward": ['treasure'], "provision": ['antivenom'],
                                             "provision_required": False, "skip": False},
    -655746259: {'name': 'PristineFountain', "reward": ['stress_heal'], "provision": ['holy_water'],
                                             "provision_required": False, "skip": False},
    1942639254: {'name': 'ShallowGrave',     "reward": ['treasure'], "provision": ['shovel'],
                                             "provision_required": True, "skip": False},
    1856562334: {'name': 'TravelersTent',    "reward": ['treasure', 'scout'], "provision": None,
                                             "provision_required": False, "skip": False},
    -1128168477: {'name': 'TroublingEffigy', "reward": ['positive_quirk'], "provision": ['holy_water'],
                                             "provision_required": True, "skip": False},

    # Cove
    660017111:   {'name': 'BarnacleCrustedChest', "reward": ['treasure'], "provision": ['shovel'],
                                                  "provision_required": False, "skip": False},
    2025661156:  {'name': 'Bas-Relief',           "reward": None, "provision": None, "provision_required": False,
                                                  "skip": True},
    1430834242:  {'name': 'BrackishTidePool',  "reward": None, "provision": ['antivenom'], "provision_required": True,
                                               "skip": True},
    -1574625474: {'name': 'EerieCoral',         "reward": ['purge_negative_quirk'], "provision": ['medicinal_herbs'],
                                                "provision_required": True, "skip": False},
    2115706125: {'name': 'FishIdol',             "reward": ['dmg_buff'], "provision": ['holy_water'],
                                                 "provision_required": True, "skip": False},
    1125882471: {'name': 'FishCarcass',          "reward": ['treasure'], "provision": ['medicinal_herbs'],
                                                 "provision_required": True, "skip": False},
    -123066604: {'name': 'GiantOyster',          "reward": ['treasure'], "provision": ['shovel'],
                                                 "provision_required": False, "skip": False},
    1837732966: {'name': 'ShipsFigurehead',      "reward": ['stress_heal', 'dmg_buff'], "provision": None,
                                                 "provision_required": False, "skip": False},

    # Courtyard
    6000000000: {'name': 'Bloodflowers',        "reward": ['treasure'], "provision": ['shovel'],
                                                "provision_required": True, "skip": False},
    6100000000: {'name': 'DamnedFountain',      "reward": ['stress_heal'], "provision": ['holy_water'],
                                                "provision_required": True, "skip": False},
    6200000000: {'name': 'DisturbingDiversion', "reward": ['treasure'], "provision": ['shovel'],
                                                "provision_required": True, "skip": False},
    6300000000: {'name': 'ForgottenDelicacies', "reward": ['treasure'], "provision": ['medicinal_herbs'],
                                                "provision_required": True, "skip": False},
    6400000000: {'name': 'HoodedShrew',         "reward": ['treasure'], "provision": ['the_blood'],
                                                "provision_required": True, "skip": False},
    6500000000: {'name': 'WizenedShrew',        "reward": ['treasure'], "provision": ['the_blood'],
                                                "provision_required": True, "skip": False},
    6600000000: {'name': 'PileOfStrangeBones',  "reward": ['treasure'], "provision": ['bandage'],
                                                "provision_required": True, "skip": False},
    6700000000: {'name': 'ThrobbingCoccoons',   "reward": ['stress_heal'], "provision": ['torch'],
                                                "provision_required": True, "skip": False},
    6800000000: {'name': 'ThrongingHive',       "reward": ['treasure'], "provision": ['torch'],
                                                "provision_required": False, "skip": False},
    6900000000: {'name': 'WineCrate',     "reward": ['firewood', 'stress_heal'], "provision": ['shovel', 'antivenom'],
                                          "provision_required": True, "skip": False},

    # Farmstead
    7100000000: {'name': 'GleamingShards',   "reward": ['treasure'], "provision": None, "provision_required": False,
                                             "skip": False},
    7200000000: {'name': 'FreshHarvest',     "reward": ['heal'], "provision": None, "provision_required": False,
                                             "skip": False},
    7300000000: {'name': 'Stockpile',        "reward": ['treasure'], "provision": ['skeleton_key'],
                                             "provision_required": False, "skip": False},
    7400000000: {'name': 'RottedFare',       "reward": ['stress_heal'], "provision": None, "provision_required": False,
                                             "skip": False},
    7500000000: {'name': 'MillersHearth',    "reward": ['camp'], "provision": None, "provision_required": False,
                                             "skip": False},
    7600000000: {'name': 'CorruptedHarvest', "reward": ['stress_heal'], "provision": None, "provision_required": False,
                                             "skip": False},
    7700000000: {'name': 'PlentifulBounty',  "reward": ['heal'], "provision": None, "provision_required": False,
                                             "skip": False},
    7800000000: {'name': 'Mildred',          "reward": ['treasure'], "provision": None, "provision_required": False,
                                             "skip": False},

    # Special
    8100000000: {'name': 'AncestorsKnapsack', "reward": ['treasure'], "provision": None, "provision_required": False,
                                              "skip": False},
    8200000000: {'name': 'TrinketChest',      "reward": ['treasure'], "provision": None, "provision_required": False,
                                              "skip": False},
    8300000000: {'name': 'ForgottenStrongbox',  "reward": ['quest_item'], "provision": None,
                                                "provision_required": False, "skip": False},
    8400000000: {'name': 'AncientArtifact',     "reward": ['treasure'], "provision": ['skeleton_key'],
                                                "provision_required": False, "skip": False},
    8500000000: {'name': 'BanditsTrappedChest', "reward": ['treasure'], "provision": ['skeleton_key'],
                                                "provision_required": True, "skip": False},
    8600000000: {'name': 'BrigandsTent',       "reward": ['treasure'], "provision": None, "provision_required": False,
                                               "skip": False},
    8700000000: {'name': 'TranscendentTerror', "reward": None, "provision": None, "provision_required": False,
                                               "skip": True},
    186284086: {'name': 'ThrobbingCoccoons',   "reward": ['fight_bloodsuckers'], "provision": None,
                                               "provision_required": False, "skip": True},

    # Quest
    -453193546: {'name': 'AnimalisticShrine', "reward": ['quest'], "provision": ['pick-axe'],
                                              "provision_required": True, "skip": False},
    693502075: {'name': 'CorruptedAltar',     "reward": ['quest'], "provision": ['consecrated_essence'],
                                              "provision_required": True, "skip": False},
    124030587: {'name': 'ChirurgeonsSack',    "reward": ['quest'], "provision": None, "provision_required": False,
                                              "skip": False},
    9300000000: {'name': 'FoodstuffCrate',    "reward": ['quest'], "provision": None, "provision_required": False,
                                              "skip": False},
    833983209:  {'name': 'InfectedCorpse',    "reward": ['quest'], "provision": ['potent_salve'],
                                              "provision_required": True, "skip": False},
    9500000000: {'name': 'IronCrown',         "reward": ['quest'], "provision": ['hand_of_glory'],
                                              "provision_required": True, "skip": False},
    9600000000: {'name': 'LocusBeacon',       "reward": ['quest'], "provision": None,
                                              "provision_required": False, "skip": False},
    286885746:  {'name': 'ProtectiveWard',    "reward": ['quest'], "provision": ['pineal_gland'],
                                              "provision_required": True, "skip": False},
    -402752115: {'name': 'Reliquary',         "reward": ['quest'], "provision": None, "provision_required": False,
                                              "skip": False},
    1231297184: {'name': 'ShipmentCrate',     "reward": ['quest'], "provision": None, "provision_required": False,
                                              "skip": False},
    9990000000: {'name': 'WinemakersReserve', "reward": ['treasure'], "provision": None, "provision_required": False,
                                              "skip": False},
}
