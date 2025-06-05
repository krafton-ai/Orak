import pydirectinput
import pyautogui
import pyscreeze
import os
import win32gui
import json
import time
import math
from pathlib import Path

from .Controls import Controller, drop_item, take_item, use_item_on_curio, combine_items
from .Items import Inventory, Item, Items
from .Curios import Curios, determine_provisions_needed
from .Battle import select_hero, get_selected_hero_rank

pydirectinput.FAILSAFE = True


def get_party_tile(raid_info, hallway_length, reverse):
    area_tile = raid_info['areatile']
    if not reverse:
        return area_tile
    return hallway_length - area_tile


def loot_treasure(raid_info, inventory, areas, area_name, party, tile_number, dungeon_path, sfr, debug):
    c = Controller(debug)
    print('Looting treasure!')
    dungeon_name = raid_info['raid_instance']['dungeon']
    queued_loot = raid_info['loot']['queue_items']['items']
    battle_reward = raid_info['loot']['result']['inventory_system']['items'] if 'result' in raid_info['loot'] else []
    c.write(c.left_stick_down)  # in case didn't exit from battle and accidentally grabbed item, let it go
    c.write(c.left_stick_up, 2)

    # check how many empty slots we have in our inventory
    item_data = {}
    for i in inventory.items:
        total = sum(item.quantity for item in inventory.items if item.name == i.name)
        stacks = math.ceil(total / i.full_stack)
        if i.name not in item_data:
            item_data.update({i.name: {'total': total, 'stacks': stacks}})
    total_stacks = sum(item['stacks'] for item in item_data.values())
    empty_slots = 16 - total_stacks
    print(f'number of empty slots in inventory: {empty_slots}')

    # combine item stacks in inventory if necessary
    items = inventory.items.copy()
    for i in items:
        items_to_combine = [item for item in inventory.items if item.name == i.name
                            and item.quantity != item.full_stack]
        for index, item in enumerate(items_to_combine):
            if index != len(items_to_combine) - 1:
                combine_items(item.item_slot, items_to_combine[index+1].item_slot, debug)
                new_item = items_to_combine[index + 1]
                leftover = item.quantity + new_item.quantity - item.full_stack
                if leftover <= 0:
                    new_item.quantity += item.quantity
                    inventory.empty_slots.append(item.item_slot)
                    inventory.items.remove(item)
                else:
                    new_item.quantity = item.full_stack
                    item.quantity = leftover
                    item.value = Items[item.name]['value'] * item.quantity if item.value is not None else item.value
                new_item.value = Items[new_item.name]['value'] * new_item.quantity if new_item.value is not None \
                    else new_item.value

    # if the loot is contained in the save file, parse it and sort it by value
    if len(queued_loot) > 0 or len(battle_reward) > 0:
        loot = [Item(item['id'], item['type'], item['amount'], item_slot)
                for item_slot, item in (queued_loot.items() if len(queued_loot) > 0 else battle_reward.items())]
        print('Specific loot contained in save file!')
        print(queued_loot if len(queued_loot) > 0 else battle_reward)

        # combine loot items with items in our inventory if possible
        # - it is assumed that items in inventory are already combined such that there can only be 1 incomplete
        #   stack per item
        for i in loot.copy():
            if i.quantity != i.full_stack:
                item = next((item for item in inventory.items if i.name == item.name
                             and item.quantity != item.full_stack), None)
                if item is not None:
                    take_item(i.item_slot, debug)
                    leftover = i.quantity + item.quantity - item.full_stack
                    if leftover <= 0:
                        item.quantity += i.quantity
                        for j in loot:
                            if j.item_slot > i.item_slot:
                                j.item_slot -= 1
                        loot.remove(i)
                    elif leftover > 0 >= empty_slots:
                        item.quantity = item.full_stack
                        i.quantity = leftover
                        i.value = Items[i.name]['value'] * i.quantity if i.value is not None else i.value
                        c.write(c.left_stick_down)
                        c.write(c.left_stick_up, 2)
                    elif leftover > 0 and empty_slots > 0:
                        item.quantity = item.full_stack
                        empty_slots -= 1
                        for j in loot:
                            if j.item_slot > i.item_slot:
                                j.item_slot -= 1
                        loot.remove(i)
                        for index in range(16):
                            if not any(j.item_slot == index for j in inventory.items):
                                inventory.items.append(Item(i.name, i.type, quantity=leftover, item_slot=index))
                                if index in inventory.empty_slots:
                                    inventory.empty_slots.remove(index)
                                break
                    item.value = Items[item.name]['value'] * item.quantity if item.value is not None else item.value
        print('Combining loot items with inventory items finished!')

        # sort loot in order of priority
        # future - add priority for stacks of heirlooms and sort
        loot_to_take = [item for item in loot if item.value is None]
        other_loot = [item for item in loot if item.value is not None]
        other_loot.sort(key=lambda k: k.value, reverse=True)
        loot_to_take.extend(other_loot)
        loot = loot_to_take.copy()

        # take items until no more empty slots
        print(f'number of empty slots in inventory: {empty_slots}')
        for index, i in enumerate(loot_to_take):
            if index < empty_slots:
                take_item(i.item_slot, debug)
                for j in loot_to_take:
                    if j.item_slot > i.item_slot:
                        j.item_slot -= 1
                for j in range(16):
                    if not any(item.item_slot == j for item in inventory.items):
                        inventory.items.append(Item(i.name, i.type, i.quantity, item_slot=j))
                        if j in inventory.empty_slots:
                            inventory.empty_slots.remove(j)
                        break
                loot.remove(i)

        # compare highest value loot with the lowest value item in our inventory
        #  to determine whether or not we should switch them
        loot_to_take = loot.copy()
        droppable_items = get_droppable_items(raid_info, areas, inventory, dungeon_name, party, dungeon_path)
        drop_count = 0
        for item in loot_to_take:
            if not ((item.type == 'trinket' and item.rating >= 6) or item.value is None
                    or item.value > droppable_items[drop_count].value):
                break
            # check again first, and only drop item if it won't combine
            # if not any(i for i in inventory.items
            #            if i.name == item.name and i.quantity + item.quantity <= i.full_stack):
            drop_item(droppable_items[drop_count].item_slot, debug)
            drop_count += 1
            take_item(item.item_slot, debug)
            for i in loot_to_take:
                if i.item_slot > item.item_slot:
                    i.item_slot -= 1
            loot.remove(item)

        if len(loot) > 0:
            c.write(c.b)
    else:
        # the loot only exists in the game client, can't determine what the items are using the save file reader
        # future - use pattern recognition to perform classification of items, for now just drop the lowest value
        #           item one at a time and take items randomly
        # loot = identify_lootscreen_items(search_region, dungeon_name, party)
        #       - Currently runs pretty fast but accuracy is terrible. Game icons are most likely being scaled
        #         and overlayed in the game in such a way that they can't recognized. Either need to create custom
        #         thumbnails instead of using game assests, or need to use a better library for image recognition
        print('Random loot, not contained in save file!')
        area_tiles = areas[area_name]['tiles']
        curio_prop = area_tiles[f'tile{tile_number}']['curio_prop']
        # rearrange inventory to fill in empty slots (must do this step!!!)
        for empty_slot in inventory.empty_slots.copy():
            print(f'filling in empty inventory slot {empty_slot}')
            last_item_slot = max(i.item_slot for i in inventory.items)
            last_item = next(item for item in inventory.items if item.item_slot == last_item_slot)
            last_slot_trinket = Items[last_item.name] if last_item.type == 'trinket' else None
            selected_hero_class = next(hero.heroClass for hero in party if hero.rank == get_selected_hero_rank())
            combine_items(last_item.item_slot, empty_slot, debug, last_slot_trinket, selected_hero_class)
            last_item.item_slot = empty_slot
            inventory.empty_slots.remove(empty_slot)

        # attempt to take all items using space
        print('attempting to take all items with space ...')
        c.write(c.right)  # needed before space command, don't remove
        pydirectinput.press(c.space, interval=.05)  # need to use pydirectinput.press for 'space'/'enter' key
        pydirectinput.press(c.space, interval=.05)  # repeat command in case input doesn't work (don't remove!)
        time.sleep(.3)
        pydirectinput.press(c.enter, interval=.05)  # close inventory full notification
        time.sleep(.3)

        sfr.decrypt_save_info('persist.map.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.map.json'))
        map_info = json.load(f)['base_root']
        f.close()
        areas = map_info['map']['static_dynamic']['areas']
        area_tile = areas[area_name]['tiles'][f'tile{tile_number}']

        # if that doesn't work, drop the lowest value item and take items until there are none left
        if area_tile['content'] != 0:
            droppable_items = get_droppable_items(raid_info, areas, inventory, dungeon_name, party, dungeon_path)

            while area_tile['content'] != 0 and len(droppable_items) > 0:
                # stop if don't want to drop lowest value item
                if ((droppable_items[0].value >= 800 and droppable_items[0].name != 'gold')
                    or (droppable_items[0].value >= 500 and droppable_items[0].name == 'gold')) \
                        and not area_name.startswith('sec') and 'quest' not in Curios[curio_prop]['reward']:
                    c.write(c.b)
                    break

                drop_item(droppable_items[0].item_slot, debug)
                # don't add gaps created to inventory.empty slots since they will always be getting filled in
                inventory.items.remove(droppable_items[0])
                droppable_items.pop(0)

                print('attempting to take all items with space ...')
                pydirectinput.press(c.space, interval=.05)  # need to use pydirectinput.press for 'space' key
                pydirectinput.press(c.space, interval=.05)  # repeat command in case doesn't work (don't remove!)
                time.sleep(.3)
                pydirectinput.press(c.enter, interval=.05)  # close inventory full notification
                pydirectinput.press(c.enter, interval=.05)  # repeat command in case doesn't work (don't remove!)
                time.sleep(.3)

                sfr.decrypt_save_info('persist.map.json')
                f = open(Path(f'{sfr.save_editor_path()}/persist.map.json'))
                map_info = json.load(f)['base_root']
                f.close()
                areas = map_info['map']['static_dynamic']['areas']
                area_tile = areas[area_name]['tiles'][f'tile{tile_number}']

    c.write(c.b, 2)  # important, make sure inventory is no longer selected
    time.sleep(.3)
    print('Looting Complete!')


def get_droppable_items(raid_info, areas, inventory, dungeon_name, party, dungeon_path):
    unscouted_rooms = len([name for name, area in areas.items() if name.startswith('roo')
                           and area['knowledge'] == 1])
    needed_provisions = determine_provisions_needed(areas, raid_info, inventory, party, dungeon_path)
    stacks_needed = Inventory.get_number_of_stacks(needed_provisions)
    stacks = inventory.numberOfStacks

    droppable_items = [item for item in inventory.items if item.value is not None
                       and item.type != 'provision' and item.type != 'gem'
                       and ((item.type == 'trinket' and item.rating < 6) or item.type != 'trinket')]

    # add extra provisions to list of possible items to drop
    provisions = [item for item in inventory.items if item.type == 'provision']
    provisions.sort(key=lambda k: k.quantity)
    for provision in provisions:
        # assign a new value for each stack of provisions depending on usefulness in each dungeon
        #   note: - values of common trinkets have been modified and citrine is worth only 150 in terms of item priority
        if stacks[provision.name] > stacks_needed[provision.name]:
            droppable_items.append(provision)
            stacks[provision.name] -= 1
        elif dungeon_name == 'crypts' and provision.name == 'holy_water' and unscouted_rooms > 1:
            provision.value = 600
            droppable_items.append(provision)
        elif dungeon_name == 'crypts' and provision.name == 'medicinal_herbs' and unscouted_rooms > 1:
            provision.value = 300
            droppable_items.append(provision)
        elif dungeon_name == 'warrens' and provision.name == 'holy_water' and unscouted_rooms > 1:
            provision.value = 300
            droppable_items.append(provision)
        elif dungeon_name == 'warrens' and provision.name == 'medicinal_herbs' and unscouted_rooms > 1:
            provision.value = 600
            droppable_items.append(provision)
        elif dungeon_name == 'weald' and provision.name == 'bandage' and unscouted_rooms > 1:
            provision.value = 600
            droppable_items.append(provision)
        elif dungeon_name == 'weald' and provision.name == 'antivenom' and unscouted_rooms > 1:
            provision.value = 400
            droppable_items.append(provision)

    # gem stacks with lower quantity are prioritized when value is the same
    gems = [item for item in inventory.items if item.type == 'gem']
    gems.sort(key=lambda k: k.quantity, reverse=True)
    droppable_items.extend(gems)
    droppable_items.sort(key=lambda k: k.value)
    return droppable_items


def activate_curio(party, provision, inventory, item, raid_info, area_name, tile_number, dungeon_path, reverse, sfr, debug):
    c = Controller(debug)

    sfr.decrypt_save_info('persist.map.json')
    f = open(Path(f'{sfr.save_editor_path()}/persist.map.json'))
    map_info = json.load(f)['base_root']
    f.close()
    areas = map_info['map']['static_dynamic']['areas']
    location = area_name
    static_areas = map_info['map']['static_dynamic']['static_save']['base_root']['areas']
    area_tiles = areas[area_name]['tiles']
    area_length = len(area_tiles) - 1
    tile_name = f'tile{tile_number}'
    curio = Curios[area_tiles[tile_name]['curio_prop']]
    print(f"Interacting with curio! ({curio['name']})")

    if provision is None and curio['name'] != 'ConfessionBooth':
        reward = curio['reward'][0] if curio['reward'] is not None else None
    elif provision is None and curio['name'] == 'ConfessionBooth':
        reward = 'purge_negative_quirk'
    else:
        reward_index = next((index for index, item in enumerate(curio['provision'])
                             if provision == item), None)
        reward = curio['reward'][reward_index] if reward_index is not None else None

    if reward is None:  # drop off quest item
        pass
    elif 'treasure' == reward:
        hero = next((hero for hero in party if 'antiquarian' == hero.heroClass), None)
        if hero is not None:
            select_hero(hero.rank, debug)
    elif 'stress_heal' == reward:
        party.sort(key=lambda k: k.stress, reverse=True)
        select_hero(party[0].rank, debug)
    elif 'purge_negative_quirk' == reward:
        # future - if heroes have the same probability, choose the one that's higher level
        removal_scores = get_quirk_removal_scores(party)
        best_score = removal_scores[0]
        if curio['name'] == 'ConfessionBooth':
            best_score = next(score for score in removal_scores
                              if next(hero for hero in party if hero.rank == score['hero_rank']).stress < 60)
        select_hero(best_score['hero_rank'], debug)
    elif 'dmg_buff' == reward:  # prioritize tier 1 dmg dealers that can hit all ranks
        dmg_dealer_rank = next((hero.rank for hero in party if hero.heroClass == 'shieldbreaker'
                                or hero.heroClass == 'highwayman' or hero.heroClass == 'hellion'), None)
        if dmg_dealer_rank is None:
            dmg_dealer_rank = next((hero.rank for hero in party if hero.heroClass == 'grave_robber'
                                    or hero.heroClass == 'crusader' or hero.heroClass == 'houndmaster'
                                    or hero.heroClass == 'flagellant' or hero.heroClass == 'man_at_arms'
                                    or hero.heroClass == 'bounty_hunter'), None)
        if dmg_dealer_rank is None:
            dmg_dealer_rank = party[0].rank
        select_hero(dmg_dealer_rank, debug)
    elif 'heal' == reward:
        party.sort(key=lambda k: k.percentHp)
        select_hero(party[0].rank, debug)
    elif 'def_buff' == reward:  # prioritize healer or non-tank heroes in ranks 1, 2, 3
        buff_target_rank = next((hero.rank for hero in party if hero.heroClass == 'vestal'
                                 or hero.heroClass == 'highwayman' or hero.heroClass == 'hellion'
                                 or hero.heroClass == 'shieldbreaker' or hero.heroClass == 'houndmaster'), None)
        if buff_target_rank is None:
            buff_target_rank = party[0].rank
        select_hero(buff_target_rank, debug)

    dd_window = win32gui.FindWindowEx(0, 0, 0, "Darkest Dungeon")
    desktop = win32gui.GetDesktopWindow()
    search_region = rf'{sfr.save_editor_path()}\search_region.png'
    hand_img = rf'{sfr.game_install_location()}\scrolls\byhand.png'
    use_item_img = rf'{sfr.game_install_location()}\scrolls\use_inventory.png'
    curio_found = False

    # don't accidentally re-enter room or secret room
    party_tile = 0 if area_length == 0 else get_party_tile(raid_info, area_length, reverse)
    if area_name.startswith('co') and area_tiles[f'tile{party_tile}']['content'] == 13 \
            and area_tiles[f'tile{party_tile}']['crit_scout'] is True:
        c.press(c.right, 25)
    elif area_length > 0 and ((party_tile == 0 and not reverse) or (party_tile == area_length and reverse)):
        c.press(c.right, 10)

    # Activate Curio
    c.write(c.up, 2)
    if not area_name.startswith('co'):
        time.sleep(1.5)  # wait for curio screen

    # if in hallway, may have to move and try again if didn't get curio
    while not raid_info['inbattle'] and area_name.startswith('co') and area_name == location:
        print('Activating curio')
        # take screenshot
        # need to minimize and reactivate window, otherwise can't see loot/curio window with a screenshot
        if not debug:
            win32gui.SetForegroundWindow(desktop)
            pydirectinput.doubleClick(x=1050, y=500)
            pydirectinput.doubleClick(x=1050, y=500)
            win32gui.SetForegroundWindow(dd_window)
            pydirectinput.doubleClick(x=1050, y=500)
            pydirectinput.doubleClick(x=1050, y=500)

            if os.path.exists(search_region):
                os.remove(search_region)
            pyautogui.screenshot(search_region, region=(1050, 390, 605, 260))
        image = use_item_img if item is not None and item.type == 'quest' else hand_img
        try:
            found = list(pyautogui.locateAll(image, search_region, confidence=.45))
        except pyscreeze.ImageNotFoundException:
            found = []
        curio_found = True if len(found) > 0 else False
        print(f'curio_found: {curio_found}')

        # move forward and try again if didn't get the curio
        sfr.decrypt_save_info('persist.raid.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
        raid_info = json.load(f)['base_root']
        f.close()
        party_tile = 0 if area_length == 0 else get_party_tile(raid_info, area_length, reverse)
        location_number = raid_info['in_area']  # 1111584611
        location = next(index for index, area in areas.items() if static_areas[index]['id'] == location_number)

        sfr.decrypt_save_info('persist.map.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.map.json'))
        map_info = json.load(f)['base_root']
        f.close()
        areas = map_info['map']['static_dynamic']['areas']
        hallway_tiles = areas[area_name]['tiles']

        if curio_found or (party_tile > tile_number and not reverse) or (party_tile < tile_number and reverse) \
                or hallway_tiles[tile_name]['content'] == 0:
            break
        c.press(c.right, 5)
        c.write(c.up, 2)
        c.write(c.b)

    if (curio_found or not area_name.startswith('co')) and area_name == location:
        if provision is None:
            if curio['name'] != 'Sack' and curio['name'] != 'DiscardedPack' and curio['name'] != 'Crate' \
                    and curio['name'] != 'Sconce':
                c.write(c.d_pad_right, 2)  # necessary to make sure curio gets past use item screen
                c.write(c.a)
                time.sleep(1.5)  # wait for potential loot screen or for save file to reflect curio has been activated
        else:
            item_used = False
            while not item_used:
                use_item_on_curio(int(item.item_slot), debug)
                # take screenshot
                # need to minimize and reactivate window, otherwise can't see loot/curio window with screenshot
                if not debug:
                    win32gui.SetForegroundWindow(desktop)
                    pydirectinput.doubleClick(x=1050, y=500)
                    pydirectinput.doubleClick(x=1050, y=500)
                    win32gui.SetForegroundWindow(dd_window)
                    pydirectinput.doubleClick(x=1050, y=500)
                    pydirectinput.doubleClick(x=1050, y=500)

                    if os.path.exists(search_region):
                        os.remove(search_region)
                    pyautogui.screenshot(search_region, region=(1290, 415, 120, 170))
                try:
                    found = list(pyautogui.locateAll(use_item_img, search_region, confidence=.8))
                except pyscreeze.ImageNotFoundException:
                    found = []
                item_used = False if len(found) > 0 else True
                print(f'item_used: {item_used}')

            item.quantity -= 1
            if item.quantity == 0:
                if item.item_slot != max(i.item_slot for i in inventory.items):
                    inventory.empty_slots.append(item.item_slot)
                inventory.items.remove(item)
        time.sleep(1.5)  # wait for potential loot screen or for save file to reflect curio has been activated

        if (reward == 'treasure' and item is not None) or (reward == 'quest' and provision is None):
            loot_treasure(raid_info, inventory, areas, area_name, party, tile_number, dungeon_path, sfr, debug)
        # check in case curio does not always give loot
        elif 'treasure' in curio['reward'] and item is None:
            if not debug:
                win32gui.SetForegroundWindow(desktop)
                pydirectinput.doubleClick(x=1050, y=500)
                pydirectinput.doubleClick(x=1050, y=500)
                win32gui.SetForegroundWindow(dd_window)
                pydirectinput.doubleClick(x=1050, y=500)
                pydirectinput.doubleClick(x=1050, y=500)

                if os.path.exists(search_region):
                    os.remove(search_region)
                c.write(c.down, 2)
                # Tried inserting button presses and sleeps to make sure icons and text doesn't get in the way
                # of screenshot. Unfortunately nothing works. Probably just have to save off custom thumbnail to look
                # for instead. Don't need to be able to see specific loot items in image anyways, since we aren't
                # performing image based classification
                pyautogui.screenshot(search_region, region=(1050, 390, 605, 235))
            try:
                found = list(pyautogui.locateAll(hand_img, search_region, confidence=.45))
            except pyscreeze.ImageNotFoundException:
                found = []
            loot_screen_found = True if len(found) > 0 else False
            print(f'loot_screen_found: {loot_screen_found}')
            if loot_screen_found:
                loot_treasure(raid_info, inventory, areas, area_name, party, tile_number, dungeon_path, sfr, debug)
    print('Activate Curio Complete!')
    # check for mission complete
    if (raid_info['raid_instance']['type'] == 'inventory_activate' and provision in Items
            and Items[provision]['type'] == 'quest' and sum(item.type == 'quest' for item in inventory.items) == 1):
        time.sleep(1.5)
        c.write(c.b, 2)


def get_quirk_removal_scores(party):
    removal_scores = []
    for each_hero in party:
        number_of_negative_quirks = sum(quirk['rating'] < 0 for quirk in each_hero.quirks)
        great_chance = 0 if number_of_negative_quirks == 0 else \
            sum(quirk['rating'] <= -8 or (quirk['rating'] == -7 and quirk['locked'] is True)
                for quirk in each_hero.quirks) / number_of_negative_quirks
        great_locks = sum(quirk['rating'] <= -7 and quirk['locked'] is True
                          for quirk in each_hero.quirks)
        good_chance = 0 if number_of_negative_quirks == 0 else \
            sum(quirk['rating'] <= -6 or (quirk['rating'] == -5 and quirk['locked'] is True)
                for quirk in each_hero.quirks) / number_of_negative_quirks
        good_locks = sum(quirk['rating'] <= -5 and quirk['locked'] is True
                         for quirk in each_hero.quirks)
        normal_chance = 0 if number_of_negative_quirks == 0 else \
            sum(quirk['rating'] <= -4 or (quirk['rating'] == -3 and quirk['locked'] is True)
                for quirk in each_hero.quirks) / number_of_negative_quirks
        normal_locks = sum(quirk['rating'] <= -3 and quirk['locked'] is True
                           for quirk in each_hero.quirks)
        removal_scores.append({'hero_rank': each_hero.rank, 'great_chance': great_chance,
                               'great_locks': great_locks, 'good_chance': good_chance, 'good_locks': good_locks,
                               'normal_chance': normal_chance, 'normal_locks': normal_locks,
                               'number_of_negative_quirks': number_of_negative_quirks})
    if not any(score['normal_chance'] > 0 or score['good_chance'] > 0 or score['great_chance'] > 0
               for score in removal_scores):
        removal_scores.sort(key=lambda k: k['number_of_negative_quirks'], reverse=True)
    else:
        removal_scores.sort(key=lambda k: k['normal_locks'], reverse=True)
        removal_scores.sort(key=lambda k: k['good_locks'], reverse=True)
        removal_scores.sort(key=lambda k: k['great_locks'], reverse=True)
        removal_scores.sort(key=lambda k: k['great_chance'], reverse=True)
        if removal_scores[0]['great_chance'] == 0:
            removal_scores.sort(key=lambda k: k['good_chance'], reverse=True)
        if removal_scores[0]['good_chance'] == 0:
            removal_scores.sort(key=lambda k: k['normal_chance'], reverse=True)
    return removal_scores


def disarm_trap(raid_info, areas, tile_number, area_name, reverse, sfr, debug):
    c = Controller(debug)
    print('Disarming Trap!')

    # don't accidentally re-enter room or secret room
    area_tiles = areas[area_name]['tiles']
    area_length = len(area_tiles) - 1
    party_tile = 0 if area_length == 0 else get_party_tile(raid_info, area_length, reverse)
    if area_name.startswith('co') and area_tiles[f'tile{party_tile}']['content'] == 13 and \
            area_tiles[f'tile{party_tile}']['crit_scout'] is True:
        c.press(c.right, 25)
    elif area_length > 0 and ((party_tile == 0 and not reverse) or (party_tile == area_length and reverse)):
        c.press(c.right, 10)

    while not raid_info['inbattle']:
        c.write(c.up)
        c.write(c.b)  # don't accidentally activate curio
        c.press(c.right, 3)

        # move forward and try again if didn't get the trap
        sfr.decrypt_save_info('persist.map.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.map.json'))
        map_info = json.load(f)['base_root']
        f.close()
        areas = map_info['map']['static_dynamic']['areas']
        area_tiles = areas[area_name]['tiles']
        area_length = len(area_tiles) - 1

        sfr.decrypt_save_info('persist.raid.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
        raid_info = json.load(f)['base_root']
        f.close()
        party_tile = 0 if area_length == 0 else get_party_tile(raid_info, area_length, reverse)
        trap = area_tiles[f'tile{tile_number}']['trap']

        # if tile_number == party_tile:
        if trap == -858993460 or trap == 0 or area_tiles[f'tile{tile_number}']['content'] == 0 \
                or (party_tile > tile_number and not reverse) or (party_tile < tile_number and reverse):
            break


def clear_obstacle(raid_info, static_areas, inventory, tile_number, area_name, reverse, sfr, debug):
    c = Controller(debug)
    print('Clearing Obstacle!')
    area_number = static_areas[area_name]['id']

    while not raid_info['inbattle']:
        shovels = [item for item in inventory.items if item.name == 'shovel']
        shovels.sort(key=lambda k: k.quantity)
        if len(shovels) > 0:
            c.write(c.y, 2)
            c.write(c.map)  # press to avoid accidentally swapping party order
            if shovels[0].quantity == 1:
                if shovels[0].item_slot != max(i.item_slot for i in inventory.items):
                    inventory.empty_slots.append(shovels[0].item_slot)
                inventory.items.remove(shovels[0])
        else:
            c.write(c.a, 2)  # pressing 'a' three times can cause unintentional party swap
            c.write(c.map)  # press to avoid accidentally swapping party order
        c.write(c.up, 2)  # if at end of hallway, obstacle is already cleared, go into next room

        # move forward and try again if didn't get the obstacle
        sfr.decrypt_save_info('persist.map.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.map.json'))
        map_info = json.load(f)['base_root']
        f.close()
        areas = map_info['map']['static_dynamic']['areas']
        area_tiles = areas[area_name]['tiles']
        area_length = len(area_tiles) - 1
        tile_name = f'tile{tile_number}'

        sfr.decrypt_save_info('persist.raid.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
        raid_info = json.load(f)['base_root']
        f.close()
        party_tile = 0 if area_length == 0 else get_party_tile(raid_info, area_length, reverse)
        location_number = raid_info['in_area']

        # if party_tile > tile_number or area_tiles[tile_name]['content'] == 0 or area_number != location_number:
        if (party_tile > tile_number and not reverse) or (party_tile < tile_number and reverse) \
                or area_tiles[tile_name]['content'] == 0 or area_number != location_number:
            break
        c.keyDown(c.right)
        time.sleep(1.5)
        c.keyUp(c.right)


def enter_room(raid_info, areas, static_areas, area_name, inventory, reverse, sfr, debug, next_room_name=None):
    c = Controller(debug)
    print('Entering Room!')
    c.write(c.b)
    area_number = static_areas[area_name]['id']

    if next_room_name is None:
        last_room_id = raid_info['last_room_id']
        last_room_name = next(room_name for room_name, data in static_areas.items() if data['id'] == last_room_id)
        last_room = Room(static_areas, last_room_name, debug)
        current_hall = next(hall for hall in last_room.connected_halls if hall['hallway_name'] == area_name)
        next_room_name = current_hall['next_room_name']

    # make sure torch is kept over 50% if there is a potential room battle
    # future - only use torch if not farmstead or courtyard
    if areas[next_room_name]['knowledge'] == 1 or areas[next_room_name]['tiles']['tile0']['mash_index'] != -1:
        torchlight = 0 if raid_info['torchlight'] == 0 else (raid_info['torchlight'] / 131072) - 8448
        buffer = 6
        torches_used = 0
        torches = [item for item in inventory.items if item.name == 'torch']
        if torchlight < 50 + buffer and len(torches) > 0:
            c.write(c.torch)
            torches_used += 1
            if torchlight < 25 + buffer:
                c.write(c.torch)
                torches_used += 1
            if torchlight < buffer:
                c.write(c.torch)
                torches_used += 1
            manage_inventory_empty_torch_slots(inventory, torches, torches_used)

    while not raid_info['inbattle']:
        # move forward and try again if didn't get the door
        sfr.decrypt_save_info('persist.map.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.map.json'))
        map_info = json.load(f)['base_root']
        f.close()
        areas = map_info['map']['static_dynamic']['areas']
        area_tiles = areas[area_name]['tiles']
        area_length = len(area_tiles) - 1

        sfr.decrypt_save_info('persist.raid.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'), encoding="utf-8")
        raid_info = json.load(f)['base_root']
        f.close()
        party_tile = get_party_tile(raid_info, area_length, reverse)
        location_number = raid_info['in_area']

        if party_tile == (area_length if not reverse else 0) or area_number != location_number:
            break
        c.keyDown(c.right)
        time.sleep(1.1)
        c.keyUp(c.right)
        c.write(c.up)
        c.write(c.b)  # if accidentally activating a curio, make sure to close out
        time.sleep(.5)  # need to give enough time for save file to update after entering room


def manage_inventory_empty_torch_slots(inventory, torches, torches_used):
    # track whether gaps were created in inventory.items
    # - assumed that the torches with the lowest slot number are used first
    leftover = None if len(torches) == 0 else torches[0].quantity - torches_used
    if leftover is not None and leftover <= 0:
        if torches[0].item_slot != max(i.item_slot for i in inventory.items):
            inventory.empty_slots.append(torches[0].item_slot)
        inventory.items.remove(torches[0])
        if leftover != 0 and len(torches) > 1:
            leftover = torches[1].quantity - leftover
            if leftover <= 0:
                if torches[1].item_slot != max(i.item_slot for i in inventory.items):
                    inventory.empty_slots.append(torches[1].item_slot)
                inventory.items.remove(torches[1])


class Room:
    def __init__(self, static_areas, room_name, debug):
        self.room_name = room_name
        self.room_number = static_areas[room_name]['id']
        self.room_coordinates = static_areas[room_name]['tiles']['tile0']['mappos']
        self.connected_halls = self.get_connected_halls(static_areas, room_name, debug)

    def get_connected_halls(self, static_areas, room_name, debug):
        c = Controller(debug)
        connected_halls = []
        for each_item, room_data in static_areas[room_name].items():
            next_room_number, next_room_coords, direction = None, None, None

            # parse connected hallway data
            if each_item.startswith('door') and room_data['area_to'] != 1701736302:
                hallway_number = room_data['area_to']
                hallway_name = next(name for name, data in static_areas.items() if data['id'] == hallway_number)
                for each_tile in static_areas[hallway_name]['tiles'].values():
                    if each_tile['type'] == 2 and each_tile['door_to']['area_to'] != self.room_number \
                            and not any(hall['next_room_number'] == each_tile['door_to']['area_to']
                                        for hall in connected_halls):
                        next_room_number = each_tile['door_to']['area_to']
                        break
                next_room_name = None if next_room_number is None \
                    else next(name for name, data in static_areas.items() if data['id'] == next_room_number)
                next_room_coords = static_areas[next_room_name]['tiles']['tile0']['mappos']

                # determine direction relative to current room
                x_diff = abs(next_room_coords[0] - self.room_coordinates[0])
                y_diff = abs(next_room_coords[1] - self.room_coordinates[1])
                if x_diff > y_diff and next_room_coords[0] > self.room_coordinates[0]:
                    direction = 'right'
                    controller_input = c.right_stick_right
                elif x_diff > y_diff and next_room_coords[0] < self.room_coordinates[0]:
                    direction = 'left'
                    controller_input = c.right_stick_left
                elif next_room_coords[1] > self.room_coordinates[1]:
                    direction = 'down'
                    controller_input = c.right_stick_down
                else:
                    direction = 'up'
                    controller_input = c.right_stick_up
                connected_halls.append({'hallway_name': hallway_name, 'hallway_number': hallway_number,
                                        'next_room_number': next_room_number, 'next_room_name': next_room_name,
                                        'direction': direction, 'controller_input': controller_input})
        return connected_halls


def identify_lootscreen_items(search_region, dungeon_name, party):
    loot = []
    thumbnail_directories = [f'{sfr.game_install_location()}/panels/icons_equip/gem',
                             f'{sfr.game_install_location()}/panels/icons_equip/gold',
                             f'{sfr.game_install_location()}/panels/icons_equip/heirloom',
                             f'{sfr.game_install_location()}/panels/icons_equip/journal_page',
                             f'{sfr.game_install_location()}/panels/icons_equip/provision',
                             f'{sfr.game_install_location()}/panels/icons_equip/supply',
                             f'{sfr.game_install_location()}/dlc/580100_crimson_court/features/'
                             f'districts/panels/icons_equip/heirloom',
                             f'{sfr.game_install_location()}/dlc/580100_crimson_court/features/'
                             f'flagellant/panels/icons_equip/trinket',
                             f'{sfr.game_install_location()}/dlc/580100_crimson_court/features/'
                             f'crimson_court/panels/icons_equip/estate',
                             f'{sfr.game_install_location()}/dlc/580100_crimson_court/features/'
                             f'crimson_court/panels/icons_equip/estate_currency', ]
    if dungeon_name == 'crimson_court':
        thumbnail_directories.append(f'{sfr.game_install_location()}/dlc/580100_crimson_court/features'
                                     f'/crimson_court/panels/icons_equip/quest_item')
        thumbnail_directories.append(f'{sfr.game_install_location()}/dlc/580100_crimson_court/features'
                                     f'/crimson_court/panels/icons_equip/trinket')
    elif dungeon_name == 'farmstead':
        thumbnail_directories.append(f'{sfr.game_install_location()}/dlc/735730_color_of_madness/panels'
                                     f'/icons_equip/heirloom')
        thumbnail_directories.append(f'{sfr.game_install_location()}/dlc/735730_color_of_madness/panels'
                                     f'/icons_equip/shard')
        thumbnail_directories.append(f'{sfr.game_install_location()}/dlc/735730_color_of_madness/panels'
                                     f'/icons_equip/supply')
        thumbnail_directories.append(f'{sfr.game_install_location()}/dlc/735730_color_of_madness/panels'
                                     f'/icons_equip/trinket')
    elif any('shieldbreaker' == hero.heroClass for hero in party) and dungeon_name != 'darkest_dungeon':
        thumbnail_directories.append(f'{sfr.game_install_location()}/dlc/702540_shieldbreaker/panels'
                                     f'/icons_equip/estate')
        thumbnail_directories.append(f'{sfr.game_install_location()}/dlc/702540_shieldbreaker/panels'
                                     f'/icons_equip/trinket')

    for directory in thumbnail_directories:
        thumbnails = os.listdir(directory)
        for thumbnail in thumbnails:
            try:
                found = list(pyautogui.locateAll(rf'{directory}\{thumbnail}', search_region, confidence=.45))
            except pyscreeze.ImageNotFoundException:
                found = []
            if len(found) > 0:
                for each_coordinates in found:
                    item_name, item_data = None, None
                    for item, data in Items.items():
                        if thumbnail in data['thumb']:
                            item_name = item
                            item_data = data
                            break

                    # future - use ocr to determine amount ???
                    if thumbnail == 'inv_gold+_0.png':
                        amount = 250
                    elif thumbnail == 'inv_gold+_1.png':
                        amount = 750
                    elif thumbnail == 'inv_gold+_2.png':
                        amount = 1250
                    elif thumbnail == 'inv_gold+_3.png':
                        amount = 1750
                    elif thumbnail == 'inv_provision+_1.png':
                        amount = 4
                    elif thumbnail == 'inv_provision+_2.png':
                        amount = 8
                    elif thumbnail == 'inv_provision+_3.png':
                        amount = 12
                    elif item_data['type'] == 'gem' or item_data['type'] == 'heirloom':
                        amount = math.floor(item_data['full_stack'] / 2)
                    else:
                        amount = 1
                    loot.append({'id': item_name, 'type': item_data['type'], 'amount': amount,
                                 'item_slot': None, 'coords': each_coordinates})
    loot.sort(key=lambda k: k['coords'][0])  # sort items from left to right
    for i, item in enumerate(loot):
        item['item_slot'] = i
    return loot