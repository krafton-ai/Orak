import math
import pyautogui
import json
from pathlib import Path
import time

from .Roster import Party, CampingSkills
from .Controls import Controller, reset_party_order, use_item
from .Battle import select_hero, use_campfire_abilities
from .Curios import Curios, provision_to_use, determine_provisions_needed
from .Items import Inventory
from .DungeonInteractions import activate_curio, clear_obstacle, disarm_trap, \
    enter_room, get_party_tile, Room, get_droppable_items, manage_inventory_empty_torch_slots

pyautogui.FAILSAFE = True

Debug = False
isKeyDown = False
RoomCounter = 0
MissionComplete = False
DungeonPath = []
RoomsPlotted = []
NextRoom = {}
respite_points = 0


def get_dungeon_path(raid_info, static_areas, location):
    global DungeonPath, MissionComplete, RoomCounter, NextRoom
    number_of_rooms = sum(name.startswith('roo') for name, data in static_areas.items())

    if RoomCounter == number_of_rooms:
        print('Mission Completed!')
        MissionComplete = True

    # Plot a route through the dungeon if there isn't one already
    if not MissionComplete and len(DungeonPath) == 0:
        print('Plotting Dungeon Route!')
        already_visited_rooms = []
        last_room, room_name = None, None
        for room_data in raid_info['stat_database']['ROOM_VISITED']['entries'].values():
            room_number = room_data['parameters']['0']['data']
            if room_number != last_room:
                room_name = next(room_name for room_name, data in static_areas.items() if room_number == data['id'])
                if room_name not in already_visited_rooms and not room_name.startswith('sec'):
                    already_visited_rooms.append(room_name)
                last_room = room_number
        # already_visited_rooms = [location]  # use for debugging to re-calculate full DungeonPath
        RoomCounter = len(already_visited_rooms)
        if RoomCounter != number_of_rooms:
            plot_dungeon_path(static_areas, number_of_rooms, current_room=room_name,
                              rooms_plotted=already_visited_rooms)
            if location.startswith('co'):
                NextRoom = DungeonPath[0]
                DungeonPath.pop(0)  # remove first item if already in hallway
    return DungeonPath, number_of_rooms


def navigate_dungeon(raid_info, areas, static_areas, inventory, party_info, location, sfr, debug):
    global Debug, RoomCounter, MissionComplete, DungeonPath, NextRoom
    Debug = debug

    print(f'Navigate Dungeon! location: {location}')
    dungeon_name = raid_info['raid_instance']['dungeon']
    party = party_info.heroes
    party_order = party_info.partyOrder
    starting_party_order = party_info.startingPartyOrder
    _, number_of_rooms = get_dungeon_path(raid_info, static_areas, location)

    # player is in a room
    if location.startswith('roo') or location.startswith('sec'):

        # interact with curio in room or skip if reward is treasure and coming back later
        tile = areas[location]['tiles']['tile0']
        curio_prop = tile['curio_prop']
        curio = None if curio_prop == 0 or tile['content'] == 0 else Curios[curio_prop]
        if curio is not None and curio['reward'] is not None \
                and ('treasure' not in curio['reward']
                     or ('stress_heal' in curio['reward'] and any(hero.stress >= 50 for hero in party))
                     or ('heal' in curio['reward'] and any(hero.OOCPercentHp <= 50 for hero in party))
                     or ('scout' in curio['reward']
                         and ((len(DungeonPath) > 0 and areas[DungeonPath[0]['next_room_name']]['knowledge'] != 3)
                              or (len(DungeonPath) > 1 and areas[DungeonPath[1]['next_room_name']][
                                    'knowledge'] != 3)))
                     or not any(hall['next_room_name'] == location for hall in DungeonPath)):
            provision, item = provision_to_use(curio_prop, areas, raid_info, party, inventory, DungeonPath)
            if not curio['skip'] and not (curio['provision_required'] and item is None):
                activate_curio(party, provision, inventory, item, raid_info, area_name=location, tile_number=0,
                               dungeon_path=DungeonPath, reverse=False, sfr=sfr, debug=Debug)
                sfr.decrypt_save_info('persist.raid.json')
                f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
                raid_info = json.load(f)['base_root']
                f.close()
                inventory = Inventory(raid_info)  # make sure to check in case items have been added

        # make sure party order is correct before entering hallway or camping
        print('Check party order! Warning: will not work if started program with party in the wrong order!')
        print(f'Starting party order: {starting_party_order}, Party order: {party_order}')
        if party_order != starting_party_order and dungeon_name != 'tutorial':
            reset_party_order(in_room=True, debug=debug)
            for hero in party:
                hero.rank = Party.get_rank(hero.roster_index, starting_party_order)

        # camp if have we have firewood and conditions are met
        if any(item.name == 'firewood' for item in inventory.items) and inventory.provision_totals['food'] >= 2:
            if len(DungeonPath) > 1:
                hallway_name = DungeonPath[0]['hallway_name']
                next_room = areas[DungeonPath[0]['next_room_name']]['tiles']['tile0']
                torchlight = 0 if raid_info['torchlight'] == 0 else (raid_info['torchlight'] / 131072) - 8448
                hallway_battle = True if any(tile['mash_index'] != -1 and tile['knowledge'] > 1
                                             for tile in areas[hallway_name]['tiles'].values()) else False
                room_battle = True if next_room['mash_index'] != -1 and next_room['knowledge'] > 1 else False
                droppable_items = get_droppable_items(raid_info, areas, inventory, dungeon_name, party, DungeonPath)
                extra_items = sum(item.type == 'provision' or (item.type == 'gem' and item.value < 400)
                                  or item.type == 'journal_page' for item in droppable_items)
                if (any(ally.percentHp <= 20 for ally in party) and sum(ally.percentHp <= 50 for ally in party) >= 2) \
                        or sum(ally.stress >= 50 for ally in party) >= 2 or any(ally.stress >= 70 for ally in party) \
                        or (len(inventory.items) - extra_items >= 15) or len(DungeonPath) == 3 \
                        or (len(inventory.items) - extra_items >= 14 and torchlight <= 25
                            and (hallway_battle or room_battle)):
                    activate_campfire(areas, raid_info, inventory, party)
            else:
                activate_campfire(areas, raid_info, inventory, party)

        select_next_room(location, areas, static_areas, number_of_rooms, sfr)

    # player is in a hall/corridor
    elif location.startswith('co'):
        static_tiles = static_areas[location]['tiles']
        hallway_tiles = areas[location]['tiles']
        hallway_length = len(hallway_tiles) - 1

        # get previous room number in order to determine travel direction
        last_room_number = raid_info['last_room_id']  # 1111584611
        last_room_tile = next(tile for tile in static_tiles
                              if last_room_number == static_tiles[tile]['door_to']['area_to'])[4:]
        next_room_number = next(area['id'] for name, area in static_areas.items() if name == NextRoom['next_room_name'])

        # don't remove, important if backtracking and debugging a curio
        next_room_tile = next((tile for tile in static_tiles
                               if next_room_number == static_tiles[tile]['door_to']['area_to']), None)
        if not Debug and next_room_tile is not None:
            reverse = True if int(next_room_tile[4:]) < int(last_room_tile) else False
        else:
            reverse = last_room_number != static_tiles['tile0']['door_to']['area_to']

        # reset party order if necessary and not on a tile with a door
        area_tile = raid_info['areatile']
        party_tile = get_party_tile(raid_info, hallway_length, reverse)
        tile_name = f'tile{party_tile}'
        print('Check party order! Warning: will not work if started program with party in the wrong order!')
        print(f'Starting party order: {starting_party_order}, Party order: {party_order}')
        if party_order != starting_party_order and area_tile != 0 and dungeon_name != 'tutorial' \
                and not (hallway_tiles[tile_name]['content'] == 13 and hallway_tiles[tile_name]['crit_scout'] is True):
            reset_party_order(in_room=False, debug=debug)
            sfr.decrypt_save_info('persist.raid.json')
            f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
            raid_info = json.load(f)['base_root']
            f.close()
            party_order = raid_info['party']['heroes']  # [front - back]
            for hero in party:
                hero.rank = Party.get_rank(hero.roster_index, party_order)

        # eat 1 food if on deaths door or can prevent deaths door
        for ally in party:
            # future - use extra items to cure blight/bleed
            if ally.currentHp == 0 \
                    or (ally.OOCPercentHp <= 0 < round(ally.maxHp * .05) + ally.currentHp - ally.damageOverTime
                        and ally.currentHp <= math.floor(ally.maxHp * .95)):
                select_hero(ally.rank, debug)
                food = [item for item in inventory.items if item.name == 'food']
                food.sort(key=lambda k: k.quantity)
                if len(food) > 0:
                    use_item(food[0].item_slot, debug)
        # choose hero to lead
        select_best_traps_hero(party, debug)

        travel_to_next_room(party, raid_info, areas, static_areas, reverse, hallway_name=location, sfr=sfr)


def select_next_room(location, areas, static_areas, number_of_rooms, sfr):
    print('Selecting next room!')
    global Debug, DungeonPath, RoomCounter, MissionComplete, NextRoom
    c = Controller(Debug)

    # Check if mission complete
    if RoomCounter == number_of_rooms:
        print('Mission Completed!')
        MissionComplete = True
        c.write(c.back)

    # Go to next room or do nothing
    if not MissionComplete and len(DungeonPath) > 0:
        c.write(c.b, 2)
        NextRoom = DungeonPath[0] if len(NextRoom) == 0 or not location.startswith('sec') else NextRoom
        controller_input = NextRoom['controller_input']
        direction = NextRoom['direction']
        # direction when leaving secret room is not always what it should be, need to try second button press
        if location.startswith('sec'):
            secret_room = Room(static_areas, location, Debug)
            last_room = next(hall['next_room_name'] for hall in secret_room.connected_halls
                             if hall['next_room_name'] != NextRoom['next_room_name'])
            next_room = NextRoom['next_room_name']
            last_room_coords = static_areas[last_room]['tiles']['tile0']['mappos']
            next_room_coords = static_areas[next_room]['tiles']['tile0']['mappos']
            x_diff = next_room_coords[0] - last_room_coords[0]
            y_diff = next_room_coords[1] - last_room_coords[1]
            button = None
            if (direction == 'up' or direction == 'down') and x_diff > 0:
                button = c.right_stick_right
            elif (direction == 'up' or direction == 'down') and x_diff < 0:
                button = c.right_stick_left
            elif (direction == 'left' or direction == 'right') and y_diff < 0:
                button = c.right_stick_up
            elif (direction == 'left' or direction == 'right') and y_diff > 0:
                button = c.right_stick_down
            if button is not None:
                print('Trying other direction input to leave secret room')
                c.write(button)
        print(f'Next Room direction: {direction}')
        c.write(controller_input)
        time.sleep(1.5)  # make sure hallway is loaded before continuing

        # make sure hallway was entered
        sfr.decrypt_save_info('persist.raid.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
        raid_info = json.load(f)['base_root']
        f.close()
        location_number = raid_info['in_area']  # 1111584611
        location = next(index for index, area in areas.items() if static_areas[index]['id'] == location_number)
        if location == NextRoom['hallway_name']:
            if areas[NextRoom['next_room_name']]['knowledge'] != 3:
                RoomCounter += 1
            DungeonPath.pop(0)


def plot_dungeon_path(static_areas, number_of_rooms, current_room, rooms_plotted, dungeon_path=None):
    """ Plots a course though the dungeon and returns a list of directional inputs """
    global DungeonPath
    if dungeon_path is None:
        dungeon_path = []
    room = Room(static_areas, room_name=current_room, debug=Debug)
    if current_room not in rooms_plotted and not current_room.startswith('sec'):
        rooms_plotted.append(current_room)

    # determine next hallway if objective not complete (haven't been to all rooms)
    if len(rooms_plotted) != number_of_rooms:
        # if len(room.connected_halls) == 1:
        #     next_hallway = room.connected_halls[0]
        if sum(hall['next_room_name'] not in rooms_plotted for hall in room.connected_halls) == 1:
            next_hallway = next(hall for hall in room.connected_halls if hall['next_room_name'] not in rooms_plotted)
        elif sum(hall['next_room_name'] not in rooms_plotted for hall in room.connected_halls) == 0:
            path_to_next_room = find_room_havent_been_to_yet(static_areas, room, rooms_plotted, dungeon_path)
            # add all rooms in path_to_next_room except for the last one
            last_room_index = len(path_to_next_room) - 1
            for i in range(last_room_index):
                hallway_name = path_to_next_room[i]['hallway_name']
                next_room = path_to_next_room[i]['next_room_name']
                direction = path_to_next_room[i]['direction']
                controller_input = path_to_next_room[i]['controller_input']
                if next_room not in rooms_plotted:
                    rooms_plotted.append(next_room)
                dungeon_path.append({'next_room_name': next_room, 'direction': direction,
                                     'hallway_name': hallway_name, 'controller_input': controller_input})
            next_hallway = path_to_next_room[last_room_index]
        else:
            possible_routes = []
            prev_rooms_plotted = [room_name for room_name in rooms_plotted]
            get_possible_routes(static_areas, current_room, prev_rooms_plotted, possible_routes)

            for route in possible_routes:
                last_room_index = len(route['path']) - 1
                next_hallway = route['path'][last_room_index]
                next_room = next_hallway['next_room_name']

                plot_dungeon_path(static_areas, number_of_rooms, next_room, route['rooms_plotted'], route['path'])

            # future - take scouting information into consideration
            # future - cheat and check where quest curios are located ???
            possible_routes.sort(key=lambda k: len(k['path']))

            # instead of adding just the next room to dungeon path, add all of the rooms in the selected route
            last_room_index = len(possible_routes[0]['path']) - 1
            for i in range(last_room_index):
                hallway_name = possible_routes[0]['path'][i]['hallway_name']
                next_room = possible_routes[0]['path'][i]['next_room_name']
                direction = possible_routes[0]['path'][i]['direction']
                controller_input = possible_routes[0]['path'][i]['controller_input']
                if next_room not in rooms_plotted:
                    rooms_plotted.append(next_room)
                dungeon_path.append({'next_room_name': next_room, 'direction': direction,
                                     'hallway_name': hallway_name, 'controller_input': controller_input})
            next_hallway = possible_routes[0]['path'][last_room_index]

        # extract the next room from the next hallway and set last room
        hallway_name = next_hallway['hallway_name']
        next_room = next_hallway['next_room_name']
        direction = next_hallway['direction']
        controller_input = next_hallway['controller_input']

        dungeon_path.append({'next_room_name': next_room, 'direction': direction,
                             'hallway_name': hallway_name, 'controller_input': controller_input})
        plot_dungeon_path(static_areas, number_of_rooms, next_room, rooms_plotted, dungeon_path)

    DungeonPath = dungeon_path


def find_room_havent_been_to_yet(static_areas, room, rooms_plotted, dungeon_path, rooms_visited=None, route=None):
    route = [] if route is None else route
    rooms_visited = [room.room_name] if rooms_visited is None else rooms_visited

    if any(hall['next_room_name'] not in rooms_plotted for hall in room.connected_halls):
        return route
    elif len(room.connected_halls) == 1:
        next_hall = room.connected_halls[0]
    elif sum(hall['next_room_name'] not in rooms_visited for hall in room.connected_halls) == 1:
        next_hall = next(hall for hall in room.connected_halls if hall['next_room_name'] not in rooms_visited)
    else:
        # determine if there are any rooms haven't been to that are 1 away
        # - may not work if the player has manually traveled to rooms outside of the calculated route
        next_hall, next_halls = None, []
        for hall in room.connected_halls:
            r = Room(static_areas, hall['next_room_name'], Debug)
            if any(h['next_room_name'] not in rooms_plotted and h['next_room_name'] not in rooms_visited
                   for h in r.connected_halls):
                next_halls.append(hall)
        if len(next_halls) == 1:
            next_hall = next_halls[0]
        else:
            # if that doesn't work, just backtrack to the first room in rooms_plotted
            index = next(i for i, r in enumerate(rooms_plotted) if r == room.room_name)
            for i in range(index - 1, -1, -1):
                next_hall = next((hall for hall in room.connected_halls
                                  if hall['next_room_name'] == rooms_plotted[i]), None)
                if next_hall is not None:
                    break

    if next_hall['next_room_name'] not in rooms_visited:
        rooms_visited.append(next_hall['next_room_name'])
    route.append(next_hall)
    next_room = Room(static_areas, next_hall['next_room_name'], Debug)
    route = find_room_havent_been_to_yet(static_areas, next_room, rooms_plotted, dungeon_path, rooms_visited, route)
    return route


def get_possible_routes(static_areas, current_room, rooms_plotted, possible_routes, dungeon_path=None):
    """ Gets a list of possible routes though the dungeon when there are multiple options """
    if dungeon_path is None:
        dungeon_path = []
    room = Room(static_areas, room_name=current_room, debug=Debug)
    if current_room not in rooms_plotted:
        rooms_plotted.append(current_room)

    number_of_rooms_left = sum(hall['next_room_name'] not in rooms_plotted for hall in room.connected_halls)

    # determine next hallway until we reach a dead end
    if number_of_rooms_left == 1:
        next_hallway = next(hall for hall in room.connected_halls if hall['next_room_name'] not in rooms_plotted)
        hallway_name = next_hallway['hallway_name']
        next_room = next_hallway['next_room_name']
        direction = next_hallway['direction']
        controller_input = next_hallway['controller_input']

        dungeon_path.append({'next_room_name': next_room, 'direction': direction,
                             'hallway_name': hallway_name, 'controller_input': controller_input})
        get_possible_routes(static_areas, next_room, rooms_plotted, possible_routes, dungeon_path)

    elif number_of_rooms_left >= 2:
        _rooms_plotted = [room_name for room_name in rooms_plotted]
        _dungeon_path = [room_path for room_path in dungeon_path]

        for each_hall in room.connected_halls:
            if each_hall['next_room_name'] in rooms_plotted:
                continue
            next_hallway = each_hall
            hallway_name = next_hallway['hallway_name']
            next_room = next_hallway['next_room_name']
            direction = next_hallway['direction']
            controller_input = next_hallway['controller_input']

            dungeon_path.append({'next_room_name': next_room, 'direction': direction,
                                 'hallway_name': hallway_name, 'controller_input': controller_input})
            get_possible_routes(static_areas, next_room, rooms_plotted, possible_routes, dungeon_path)
            if not any(route['path'] == dungeon_path for route in possible_routes):
                possible_routes.append({'path': [room_path for room_path in dungeon_path],
                                        'rooms_plotted': rooms_plotted})

            rooms_plotted = [room_name for room_name in _rooms_plotted]
            dungeon_path = [room_path for room_path in _dungeon_path]


def travel_to_next_room(party, raid_info, areas, static_areas, reverse, hallway_name, sfr,
                        inventory=None, skip_hunger_check=False):
    global Debug, DungeonPath, NextRoom
    print('Traveling to next room!')
    inventory = Inventory(raid_info) if inventory is None else inventory
    static_tiles = static_areas[hallway_name]['tiles']
    hallway_tiles = areas[hallway_name]['tiles']
    hallway_length = len(hallway_tiles) - 1

    # make a list for remaining tiles in hallway, taking direction of travel into account
    party_tile = get_party_tile(raid_info, hallway_length, reverse)
    if not reverse:
        tiles_to_navigate = list(range(party_tile, hallway_length))
    else:
        tiles_to_navigate = list(range(party_tile, 0, -1))

    # Determine next hallway interaction
    # - it's rare but if party tile doesn't update in save file for some reason, just need to close and reopen the game
    hallway_battle = False
    print(f'tiles to navigate: {tiles_to_navigate}')
    for i in tiles_to_navigate:
        tile_name = f'tile{i}'
        if not hallway_battle:  # assume there could be a hallway battle if not scouted
            scouted = True if hallway_tiles[tile_name]['knowledge'] > 1 else False
            if not scouted or (scouted and hallway_tiles[tile_name]['mash_index'] != -1):
                hallway_battle = True
        curio_prop = hallway_tiles[tile_name]['curio_prop']

        # hunger check
        if hallway_tiles[tile_name]['content'] == 8 and not skip_hunger_check:
            print('moving to hunger check')
            # move right up to the beginning of the tile containing the hunger check
            move_to_tile(raid_info, hallway_length, inventory, reverse, tile_number=i, battle=hallway_battle, sfr=sfr)
            sfr.decrypt_save_info('persist.raid.json')
            f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
            raid_info = json.load(f)['base_root']
            f.close()
            if not raid_info['inbattle']:
                hunger_check(areas, static_areas, inventory, party, hallway_name, reverse, sfr, debug=Debug)
            break
        # Curio - skip if we're returning later and get it on the way back
        curio = None if curio_prop == 0 or hallway_tiles[tile_name]['content'] == 0 else Curios[curio_prop]
        if curio is not None and curio['reward'] is not None \
                and ('treasure' not in curio['reward']
                     or ('stress_heal' in curio['reward'] and any(hero.stress >= 50 for hero in party))
                     or ('heal' in curio['reward'] and any(hero.OOCPercentHp <= 50 for hero in party))
                     or ('scout' in curio['reward'] and ((len(DungeonPath) > 0 and areas[DungeonPath[0]['next_room_name']]['knowledge'] != 3)
                                                         or (len(DungeonPath) > 1 and areas[DungeonPath[1]['next_room_name']]['knowledge'] != 3)))
                     or not any(hall['hallway_name'] == hallway_name for hall in DungeonPath)):
            provision, item = provision_to_use(curio_prop, areas, raid_info, party, inventory, DungeonPath)
            if not (curio['skip'] or (curio['provision_required'] and item is None)
                    or (curio['name'] == 'ConfessionBooth' and not any(hero.stress < 60 for hero in party))):
                print(f"moving to curio {curio['name']}")
                # - can't reliably use move_to_tile to move right up to the same tile as curio without moving past it
                # - make sure to walk past other curio if we are skipping it
                if abs(party_tile - i) == 2 and (party_tile == 0 or party_tile == hallway_length):
                    c = Controller(Debug)
                    c.keyDown(c.right)
                    time.sleep(1.1)  # previous value 1.2
                    c.keyUp(c.right)
                elif abs(party_tile - i) > 1:
                    tile = i - 1 if not reverse else i + 1
                    move_to_tile(raid_info, hallway_length, inventory, reverse, tile_number=tile, battle=hallway_battle, sfr=sfr)
                    # - get closer to tile with curio and make sure to walk past other curio if we are skipping it
                    c = Controller(Debug)
                    c.keyDown(c.right)
                    time.sleep(1.1)  # previous value 1.2
                    c.keyUp(c.right)
                    sfr.decrypt_save_info('persist.raid.json')
                    f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
                    raid_info = json.load(f)['base_root']
                    f.close()
                if not raid_info['inbattle']:
                    activate_curio(party, provision, inventory, item, raid_info, area_name=hallway_name,
                                   tile_number=i, dungeon_path=DungeonPath, reverse=reverse, sfr=sfr, debug=Debug)
                break
        # Trap
        trap = hallway_tiles[tile_name]['trap']
        if trap != -858993460 and trap != 0 and hallway_tiles[tile_name]['knowledge'] > 1 \
                and hallway_tiles[tile_name]['content'] == 3:
            print('moving to trap')
            # - can't reliably use move_to_tile to move right up to the same tile as the trap without moving past it
            # - make sure to walk past curio if we are skipping it
            if abs(party_tile - i) == 2 and (party_tile == 0 or party_tile == hallway_length):
                c = Controller(Debug)
                c.keyDown(c.right)
                time.sleep(1.1)  # previous value 1.2
                c.keyUp(c.right)
            elif abs(party_tile - i) > 1:
                tile = i - 1 if not reverse else i + 1
                move_to_tile(raid_info, hallway_length, inventory, reverse, tile_number=tile, battle=hallway_battle, sfr=sfr)
                # - get closer to tile with trap and make sure to walk past curio if we are skipping it
                c = Controller(Debug)
                c.keyDown(c.right)
                time.sleep(1.1)  # previous value 1.2
                c.keyUp(c.right)
                sfr.decrypt_save_info('persist.raid.json')
                f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
                raid_info = json.load(f)['base_root']
                f.close()
            if not raid_info['inbattle']:
                disarm_trap(raid_info, areas, tile_number=i, area_name=hallway_name, reverse=reverse, sfr=sfr, debug=Debug)
            break
        # secret room - skip if we're returning later and get it on the way back
        secret_room = next((room for room_name, room in areas.items() if room_name.startswith('sec')), None)
        if hallway_tiles[tile_name]['content'] == 13 and hallway_tiles[tile_name]['crit_scout'] is True \
                and not any(hall['hallway_name'] == hallway_name for hall in DungeonPath) \
                and secret_room['tiles']['tile0']['content'] != 0:
            print('moving to secret room')
            move_to_tile(raid_info, hallway_length, inventory, reverse, tile_number=i, battle=hallway_battle, sfr=sfr)
            sfr.decrypt_save_info('persist.raid.json')
            f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
            raid_info = json.load(f)['base_root']
            f.close()
            if not raid_info['inbattle']:
                enter_secret_room(static_areas, raid_info, reverse, Debug)
            break
        # clear obstacle
        obstacle = static_tiles[tile_name]['obstacle']
        if obstacle != -858993460 and obstacle != 0 and hallway_tiles[tile_name]['content'] != 0:
            print('moving to obstacle')
            move_to_tile(raid_info, hallway_length, inventory, reverse, tile_number=i, battle=hallway_battle, sfr=sfr)
            sfr.decrypt_save_info('persist.raid.json')
            f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
            raid_info = json.load(f)['base_root']
            f.close()
            if not raid_info['inbattle']:
                clear_obstacle(raid_info, static_areas, inventory, tile_number=i, area_name=hallway_name,
                               reverse=reverse, sfr=sfr, debug=Debug)
            break
        # end of hallway
        if i == (hallway_length - 1 if not reverse else 1):
            print('moving to next room')
            move_to_tile(raid_info, hallway_length, inventory, reverse, tile_number=i, battle=hallway_battle, sfr=sfr)
            sfr.decrypt_save_info('persist.raid.json')
            f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
            raid_info = json.load(f)['base_root']
            f.close()
            if not raid_info['inbattle']:
                enter_room(raid_info, areas, static_areas, hallway_name, inventory, reverse=reverse, sfr=sfr,
                           debug=Debug, next_room_name=NextRoom['next_room_name'])
            break


def hunger_check(areas, static_areas, inventory, party, hallway_name, reverse, sfr, debug):
    global DungeonPath
    c = Controller(debug)
    print('Hunger Check!')

    # move till we get to hunger check
    # - needs to be long enough to trigger the hunger check, but not walk past the next curio
    # - ideally this should just be the length of a single tile
    c.keyDown(c.right)
    time.sleep(1.1)  # previous value 1.2
    c.keyUp(c.right)
    c.write(c.y, 2)  # try for now in case it helps when hunger check is next
    c.write(c.map)  # press to avoid accidentally swapping party order

    # hit 'a' to use food on hunger check or 'b' if not enough food
    food = [item for item in inventory.items if item.name == 'food']
    total_food = inventory.provision_totals['food']
    if total_food >= 4:
        c.write(c.a, 2)  # beware, pressing 'a' three times can cause unintentional party swap
        c.write(c.map)  # press to avoid accidentally swapping party order
    else:
        c.write(c.b, 2)
    time.sleep(.3)

    # manage gaps in inventory.items
    sfr.decrypt_save_info('persist.raid.json')
    f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
    raid_info = json.load(f)['base_root']
    f.close()
    inventory = Inventory(raid_info)
    location_number = raid_info['in_area']  # 1111584611
    location = next(index for index, area in areas.items() if static_areas[index]['id'] == location_number)

    if inventory.provision_totals['food'] < total_food:
        food.sort(key=lambda k: k.item_slot, reverse=True)
        food.sort(key=lambda k: k.quantity)
        food[0].quantity -= 4
        if food[0].quantity <= 0:
            if food[0].item_slot != max(i.item_slot for i in inventory.items):
                inventory.empty_slots.append(food[0].item_slot)
            if food[0].quantity < 0:
                food[1].quantity += food[0].quantity
                if food[1].quantity <= 0 and food[1].item_slot != max(i.item_slot for i in inventory.items):
                    inventory.empty_slots.append(food[1].item_slot)
            inventory = Inventory(raid_info)

    # Proceed to next hallway interaction
    # - sometimes hunger check does not go off, and when that happens save file does not update until moving past
    #   the next curio or entering next room
    if location == hallway_name:
        travel_to_next_room(party, raid_info, areas, static_areas, reverse, hallway_name, sfr, inventory, True)


def enter_secret_room(static_areas, raid_info, reverse, debug):
    global DungeonPath, NextRoom
    c = Controller(debug)
    print('Entering Secret Room!')
    # Don't accidentally re-enter room
    area_length = len(static_areas) - 1
    party_tile = 0 if area_length == 0 else get_party_tile(raid_info, area_length, reverse)
    if area_length > 0 and ((party_tile == 0 and not reverse) or (party_tile == area_length and reverse)):
        c.press(c.right, 10)

    while True:
        c.write(c.up)
        c.write(c.b)
        time.sleep(.3)
        sfr.decrypt_save_info('persist.raid.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
        raid_info = json.load(f)['base_root']
        f.close()
        if raid_info['inbattle']:
            break
        location_number = raid_info['in_area']  # 1111584611
        location = next(index for index, area in static_areas.items() if static_areas[index]['id'] == location_number)
        if not location.startswith('co'):
            # future - snuff torch
            DungeonPath.insert(0, NextRoom)
            break
        c.press(c.right, 5)


def move_to_tile(raid_info, hallway_length, inventory, reverse, tile_number, battle, sfr):
    global isKeyDown
    c = Controller(Debug)
    torches_used, loop_count = 0, 0  # useful in case stuck on hunger check or an obstacle
    party_tile = get_party_tile(raid_info, hallway_length, reverse)
    distance = tile_number - party_tile if not reverse else party_tile - tile_number
    torches = [item for item in inventory.items if item.name == 'torch']
    print(f'party on tile{party_tile}, moving to tile{tile_number}!')

    # make sure to use torch a before moving if there could be a hallway battle
    torchlight = 0 if raid_info['torchlight'] == 0 else (raid_info['torchlight'] / 131072) - 8448
    if torchlight < 25 and battle:
        c.write(c.torch)
        manage_inventory_empty_torch_slots(inventory, torches, torches_used=1)

    # move to tile with next dungeon interaction
    while party_tile != tile_number and not raid_info['inbattle'] and loop_count < distance * 12:
        if not isKeyDown:
            c.keyDown(c.right)
            isKeyDown = True

        sfr.decrypt_save_info('persist.raid.json')
        f = open(Path(f'{sfr.save_editor_path()}/persist.raid.json'))
        raid_info = json.load(f)['base_root']
        f.close()

        # make sure torch is kept over 50% if there is a potential hallway battle
        # future - only use torch if not farmstead or courtyard
        if battle:
            torchlight = 0 if raid_info['torchlight'] == 0 else (raid_info['torchlight'] / 131072) - 8448
            buffer = (distance - 1) * 6
            if torches_used == 0 and torchlight < 50 + buffer and len(torches) > 0:
                c.write(c.torch)
                torches_used += 1
                if torchlight < 25 + buffer:
                    c.write(c.torch)
                    torches_used += 1
                if torchlight < buffer:
                    c.write(c.torch)
                    torches_used += 1

        party_tile = get_party_tile(raid_info, hallway_length, reverse)
        loop_count += 1

    if isKeyDown:
        c.keyUp(c.right)
        isKeyDown = False
    torches = [item for item in inventory.items if item.name == 'torch']
    manage_inventory_empty_torch_slots(inventory, torches, torches_used)


def select_best_traps_hero(party, debug):
    print('Select traps hero')
    hero = None
    heroes = []
    for each_hero in party:
        if each_hero.traps_skill >= 30:
            heroes.append(each_hero)
    if len(heroes) > 0:
        heroes.sort(key=lambda k: k.stress, reverse=True)
        hero = next((hero for hero in heroes if hero.stress <= 70 and hero.percentHp >= 20), None)
    if hero is None and len(heroes) > 0:
        heroes.sort(key=lambda k: k.effectiveHp, reverse=True)
        hero = heroes[0]
    if hero is None:
        party.sort(key=lambda k: k.stress)
        hero = next((hero for hero in party if hero.stress <= 70 and hero.percentHp >= 35), None)
    if hero is None:
        party.sort(key=lambda k: k.effectiveHp, reverse=True)
        hero = party[0]
    select_hero(target_hero_rank=hero.rank, debug=debug)


def activate_campfire(areas, raid_info, inventory, party):
    global Debug, DungeonPath
    c = Controller(Debug)
    print('Activating Campfire')
    wood = next(item for item in inventory.items if item.name == 'firewood')
    use_item(int(wood.item_slot), Debug)
    time.sleep(2.5)
    if wood.quantity == 1 and wood.item_slot != max(i.item_slot for i in inventory.items):
        inventory.empty_slots.append(wood.item_slot)
    # determine how much food to use (future - take quirks/trinkets into account)
    needed_provisions = determine_provisions_needed(areas, raid_info, inventory, party, DungeonPath)
    offset, used = 0, 0
    if (any(ally.stress >= 30 for ally in party) or sum(ally.stress >= 20 for ally in party) >= 2) \
            and inventory.provision_totals['food'] >= needed_provisions['food'] + 8:
        used = 8
        offset = 3
    elif (any(ally.percentHp <= 85 for ally in party) or sum(ally.percentHp < 100 for ally in party) >= 2) \
            and inventory.provision_totals['food'] >= needed_provisions['food'] + 4:
        used = 4
        offset = 2
    elif inventory.provision_totals['food'] >= 2:
        used = 2
        offset = 1
    print(f'using {used} food!')

    # need to add empty slots for food
    if inventory.provision_totals['food'] >= 2:
        food = [item for item in inventory.items if item.name == 'food']
        food.sort(key=lambda k: k.item_slot, reverse=True)
        food.sort(key=lambda k: k.quantity)
        leftover = used - food[0].quantity
        if leftover >= 0:
            if food[0].item_slot != max(i.item_slot for i in inventory.items):
                print(f'assuming food stacks are used from right to left, empty slot on {food[0].item_slot}')
                inventory.empty_slots.append(food[0].item_slot)
            if used - food[1].quantity >= 0 and food[1].item_slot != max(i.item_slot for i in inventory.items):
                inventory.empty_slots.append(food[1].item_slot)
    c.write(c.left_stick_right, offset)
    c.write(c.a)
    time.sleep(2.0)
    # future - take into account healing buffs
    if used == 8:
        for hero in party:
            hero.update_hp(25)
            hero.stress -= 10
            hero.stress = 0 if hero.stress < 0 else hero.stress
    elif used == 4:
        for hero in party:
            hero.update_hp(10)
    if used >= 2:
        select_campfire_abilities(party)
    time.sleep(2.5)


def select_campfire_abilities(party):
    global respite_points
    c = Controller(Debug)
    respite_points = 12
    camping_skills, camping_skills_to_use = [], []
    print('Selecting Campfire Abilities!')
    for ally in party:
        for skill_slot, skill in enumerate(ally.campingSkills):
            camping_skills.append({'skill_name': skill, 'effect': CampingSkills[skill]['effect'],
                                   'cost': CampingSkills[skill]['cost'], 'target': CampingSkills[skill]['target'],
                                   'hero_rank': ally.rank, 'skill_slot': skill_slot})
    # remove diseases
    disease_skills = [skill for skill in camping_skills if 'cure_disease' in skill['effect']]
    diseased_heroes = [hero for hero in party if len(hero.diseases) > 1
                       or (len(hero.diseases) == 1 and 'crimson_curse' in hero.diseases)]
    disease_skills.sort(key=lambda k: k['cost'])  # use lowest cost skills first
    for hero in diseased_heroes:
        for skill in disease_skills.copy():
            if skill['target'] == 'any' \
                    or skill['target'] == 'all' or (hero.rank == skill['hero_rank'] and skill['target'] == 'self') \
                    or (hero.rank != skill['hero_rank']
                        and (skill['target'] == 'ally' or skill['target'] == 'allies')) \
                    and skill['cost'] <= respite_points:

                camping_skills_to_use.append({'skill': skill, 'target': hero.rank})
                respite_points -= skill['cost']
                disease_skills.remove(skill)
                camping_skills.remove(skill)
                break

    # if have non-ambush skill and no shieldbreaker
    ambush_skills = [skill for skill in camping_skills if 'no_ambush' in skill['effect']]
    if not any(ally.heroClass == 'shieldbreaker' for ally in party) and len(ambush_skills) > 0:
        # sanctuary = next((skill for skill in ambush_skills if skill['skill_name'] == 'sanctuary'), None)
        bandit_sense_or_hounds_watch = next((skill for skill in ambush_skills if skill['skill_name'] == 'bandits_sense'
                                             or skill['skill_name'] == 'hounds_watch'), None)
        # future - if any ally has a mortality debuff (need to check how ???), use sanctuary
        party.sort(key=lambda k: k.stress, reverse=True)
        zealous_vigil_rank = next((hero.rank for hero in party if 'zealous_vigil'
                                   in hero.campingSkills and hero.stress > 15), None)
        if zealous_vigil_rank is not None:
            skill = next(skill for skill in ambush_skills if skill['hero_rank'] == zealous_vigil_rank
                         and skill['skill_name'] == 'zealous_vigil')
        elif bandit_sense_or_hounds_watch is not None:
            skill = bandit_sense_or_hounds_watch
        else:
            skill = ambush_skills[0]
        camping_skills_to_use.append({'skill': skill, 'target': 0})
        respite_points -= skill['cost']
        camping_skills.remove(skill)

    # group stress heal
    select_group_stress_heal_campfire_skill(party, camping_skills, camping_skills_to_use)

    # really need heal
    select_heal_campfire_skill(40, party, camping_skills, camping_skills_to_use)

    # scouting boost - only one skill in the whole game
    scout_skill = next((skill for skill in camping_skills if 'scout' in skill['effect']), None)
    if scout_skill is not None and scout_skill['cost'] <= respite_points:
        camping_skills_to_use.append({'skill': scout_skill, 'target': 0})
        respite_points -= scout_skill['cost']
        camping_skills.remove(scout_skill)

    # future - remove mortality debuffs

    # stress heal
    select_single_stress_heal_campfire_skill(15, party, camping_skills, camping_skills_to_use)

    # buffs
    # future - prep for shieldbreaker night ambush
    # - snake_skin
    # - adders embrace
    # - pray
    if respite_points >= 3 and respite_points != 4:
        select_tier_1_campfire_buffs(party, camping_skills, camping_skills_to_use, stop_on_four=True)

    if respite_points >= 4:
        select_party_campfire_buffs(camping_skills, camping_skills_to_use)

    if respite_points >= 3:
        select_tier_1_campfire_buffs(party, camping_skills, camping_skills_to_use, stop_on_four=False)

    if respite_points >= 3:
        select_tier_2_campfire_buffs(camping_skills, camping_skills_to_use)

    # spend leftover points
    if any(ally.stress >= 30 for ally in party) and respite_points >= 2:
        select_single_stress_heal_campfire_skill(30, party, camping_skills, camping_skills_to_use)

    if any(ally.OOCPercentHp <= 70 for ally in party) and respite_points >= 2:
        select_heal_campfire_skill(70, party, camping_skills, camping_skills_to_use)

    if any(ally.stress >= 1 for ally in party) and respite_points >= 2:
        select_single_stress_heal_campfire_skill(1, party, camping_skills, camping_skills_to_use)

    if any(ally.OOCPercentHp <= 99 for ally in party) and respite_points >= 2:
        select_heal_campfire_skill(99, party, camping_skills, camping_skills_to_use)

    # use campfire abilities
    print(camping_skills_to_use)
    use_campfire_abilities(camping_skills_to_use)
    c.write(c.y, 2)
    c.write(c.b, 4)


def select_group_stress_heal_campfire_skill(party, camping_skills, camping_skills_to_use):
    print('Select Group Stress Heal!')
    global respite_points
    single_stress_skills = [skill for skill in camping_skills if 'stress_heal' in skill['effect']
                            and (skill['target'] == 'self' or skill['target'] == 'ally' or skill['target'] == 'any')]
    while sum(hero.stress > 0 for hero in party) > 1 \
            or (sum(hero.stress >= 10 for hero in party) == 1 and len(single_stress_skills) == 0):
        # skip if no group stress skills or not enough respite points
        if not any('stress_heal' in skill['effect'] and (skill['target'] == 'all' or skill['target'] == 'allies')
                   and skill['cost'] <= respite_points for skill in camping_skills):
            break
        group_stress_skills = []
        for skill in camping_skills:
            if 'stress_heal' in skill['effect'] and (skill['target'] == 'all' or skill['target'] == 'allies'):
                if skill['skill_name'] == 'pray':
                    stress_healed = sum((15 if hero.stress > 15 else hero.stress)
                                        if (hero.heroClass == 'crusader' or hero.heroClass == 'vestal'
                                            or hero.heroClass == 'flagellant' or hero.heroClass == 'leper')
                                        else (5 if hero.stress > 5 else hero.stress)
                                        for hero in party if hero.rank != skill['hero_rank'])
                elif skill['target'] == 'allies':
                    stress_healed = sum(skill['effect']['stress_heal'] if hero.stress > skill['effect']['stress_heal']
                                        else hero.stress for hero in party if hero.rank != skill['hero_rank'])
                else:
                    stress_healed = sum(skill['effect']['stress_heal'] if hero.stress > skill['effect']['stress_heal']
                                        else hero.stress for hero in party)
                group_stress_skills.append({'skill': skill, 'total_stress_healed': stress_healed})
        # prioritize primarily by amount of stress healed, and secondarily by cost
        group_stress_skills.sort(key=lambda k: k['skill']['cost'])
        group_stress_skills.sort(key=lambda k: k['total_stress_healed'], reverse=True)
        skill_to_use = next(skill for skill in group_stress_skills if skill['skill']['cost'] <= respite_points)

        camping_skills_to_use.append({'skill': skill_to_use['skill'], 'target': 0})
        respite_points -= skill_to_use['skill']['cost']
        # update party stress
        for ally in party:
            if skill_to_use['skill']['target'] == 'all' \
                    or (skill_to_use['skill']['target'] == 'allies' and ally.rank != skill_to_use['skill']['hero_rank']):
                if skill_to_use['skill']['skill_name'] == 'pray':
                    stress_healed = 15 if ally.heroClass == 'crusader' or ally.heroClass == 'vestal' \
                                          or ally.heroClass == 'flagellant' or ally.heroClass == 'leper' else 5
                    ally.stress -= stress_healed
                else:
                    ally.stress -= skill_to_use['skill']['effect']['stress_heal']
                ally.stress = 0 if ally.stress < 0 else ally.stress
        camping_skills.remove(skill_to_use['skill'])


def select_single_stress_heal_campfire_skill(threshold, party, camping_skills, camping_skills_to_use):
    print('Select Single Stress Heal!')
    global respite_points
    # prioritize skills by amount healed, and secondarily by cost
    stress_skills = [skill for skill in camping_skills if 'stress_heal' in skill['effect']
                     and (skill['target'] == 'any' or skill['target'] == 'self' or skill['target'] == 'ally')]
    stress_skills.sort(key=lambda k: k['cost'])
    stress_skills.sort(key=lambda k: k['effect']['stress_heal'], reverse=True)
    turn_back_times = [skill for skill in camping_skills if skill['skill_name'] == 'turn_back_time']  # jester ability

    while len(stress_skills) > 0 and any(skill['cost'] <= respite_points for skill in stress_skills):
        stressed_allies = [ally for ally in party if ally.stress >= threshold]
        if len(stressed_allies) == 0 or not any(skill['target'] == 'any'
                                                or (skill['target'] == 'self' and skill['hero_rank'] == hero.rank)
                                                or (skill['target'] == 'ally' and skill['hero_rank'] != hero.rank)
                                                for skill in stress_skills for hero in stressed_allies):
            break

        stressed_allies.sort(key=lambda k: k.stress, reverse=True)
        for hero in stressed_allies:
            turn_back_time = next((skill for skill in turn_back_times
                                   if (hero.stress >= 25 or (hero.stress > 15 and respite_points >= 5)
                                       or not any(stress_skill['skill_name'] != 'turn_back_time' in stress_skills
                                                  for stress_skill in stress_skills)) and skill[
                                       'hero_rank'] != hero.rank), None)
            if turn_back_time is not None and turn_back_time['cost'] <= respite_points:
                stress_skill = turn_back_time
            else:
                stress_skill = next((skill for skill in stress_skills if skill['skill_name'] != 'turn_back_time' and
                                     (skill['target'] == 'any'
                                      or (skill['target'] == 'self' and skill['hero_rank'] == hero.rank)
                                      or (skill['target'] == 'ally' and skill['hero_rank'] != hero.rank))), None)

            if stress_skill is not None and stress_skill['cost'] <= respite_points:
                camping_skills_to_use.append({'skill': stress_skill, 'target': hero.rank})
                respite_points -= stress_skill['cost']
                # update ally stress
                if (stress_skill['target'] == 'ally' and hero.rank != stress_skill['hero_rank']) \
                        or (stress_skill['target'] == 'self' and hero.rank == stress_skill['hero_rank']) \
                        or stress_skill['target'] == 'any':
                    hero.stress -= stress_skill['effect']['stress_heal']
                    hero.stress = 0 if hero.stress < 0 else hero.stress
                camping_skills.remove(stress_skill)
                stress_skills.remove(stress_skill)
                break


def select_heal_campfire_skill(threshold, party, camping_skills, camping_skills_to_use):
    print('Select Heal Campfire Skill!')
    global respite_points
    # prioritize skills by amount healed, and secondarily by cost
    heal_skills = [skill for skill in camping_skills if 'heal' in skill['effect']]
    heal_skills.sort(key=lambda k: k['cost'])
    heal_skills.sort(key=lambda k: k['effect']['heal'], reverse=True)

    while len(heal_skills) > 0 and any(skill['cost'] <= respite_points for skill in heal_skills):
        low_hp_allies = [ally for ally in party if ally.OOCPercentHp <= threshold]  # out-of-combat hp
        if len(low_hp_allies) == 0 or not any(skill['target'] == 'any'
                                              or (skill['target'] == 'self' and skill['hero_rank'] == hero.rank)
                                              or (skill['target'] == 'ally' and skill['hero_rank'] != hero.rank)
                                              for skill in heal_skills for hero in low_hp_allies):
            break

        low_hp_allies.sort(key=lambda k: k.OOCPercentHp)
        for hero in low_hp_allies:
            heal_skill = next((skill for skill in heal_skills if skill['target'] == 'any' or skill['target'] == 'all'
                               or (skill['target'] == 'self' and skill['hero_rank'] == hero.rank)
                               or ((skill['target'] == 'ally' or skill['target'] == 'allies')
                                   and skill['hero_rank'] != hero.rank)), None)
            if heal_skill is not None and heal_skill['cost'] <= respite_points:
                camping_skills_to_use.append({'skill': heal_skill, 'target': hero.rank})
                respite_points -= heal_skill['cost']
                # update party hp
                for ally in party:
                    if heal_skill['target'] == 'all' or heal_skill['target'] == 'any' \
                            or ((heal_skill['target'] == 'allies' or heal_skill['target'] == 'ally')
                                and ally.rank != heal_skill['hero_rank']) \
                            or (heal_skill['target'] == 'self' and hero.rank == ally.rank):
                        ally.currentHp += (heal_skill['effect']['heal'] / 100) * ally.maxHp
                        ally.currentHp = ally.maxHp if ally.maxHp < ally.currentHp else ally.currentHp
                        if 'heal_blight' in heal_skill['effect']:
                            ally.blightAmount = 0
                            ally.blightDuration = 0
                        if 'heal_bleed' in heal_skill['effect']:
                            ally.bleedAmount = 0
                            ally.bleedDuration = 0
                        ally.damageOverTime = ally.bleedAmount * ally.bleedDuration + ally.blightAmount * ally.blightDuration
                        ally.OOCPercentHp = ((ally.currentHp - ally.damageOverTime) / ally.maxHp) * 100  # out-of-combat
                camping_skills.remove(heal_skill)
                heal_skills.remove(heal_skill)
                break


def select_tier_1_campfire_buffs(party, camping_skills, camping_skills_to_use, stop_on_four):
    print('Select Tier 1 Buffs')
    global respite_points
    # accuracy buffs + pray (all 3 respite points)
    pray = next((skill for skill in camping_skills if skill['skill_name'] == 'pray'), None)
    tigers_eye = next((skill for skill in camping_skills if skill['skill_name'] == 'tigers_eye'), None)
    instruction = next((skill for skill in camping_skills if skill['skill_name'] == 'instruction'), None)
    self_medicate = next((skill for skill in camping_skills if skill['skill_name'] == 'self_medicate'), None)
    bless = next((skill for skill in camping_skills if skill['skill_name'] == 'bless'), None)

    if pray is not None and sum(ally.stress >= 5 for ally in party) >= 2 \
            and respite_points >= 3 and not (respite_points == 4 and stop_on_four):
        camping_skills_to_use.append({'skill': pray, 'target': 0})
        respite_points -= pray['cost']
        camping_skills.remove(pray)
    if tigers_eye is not None and ((respite_points >= 3 and not stop_on_four)
                                   or ((respite_points == 3 or respite_points >= 7) and stop_on_four)):
        target = next((hero for hero in party if 'acc_buff' not in hero.buffs and (hero.heroClass == 'hellion'
                       or hero.heroClass == 'shieldbreaker' or hero.heroClass == 'highwayman')), None)
        if target is None:
            target = next((hero for hero in party if 'acc_buff' not in hero.buffs
                           and hero.heroClass == 'crusader'), None)
        if target is None:
            target = next((hero for hero in party if 'acc_buff' not in hero.buffs
                           and (hero.heroClass == 'man_at_arms' or hero.heroClass == 'houndmaster')), None)
        if target is not None:
            camping_skills_to_use.append({'skill': tigers_eye, 'target': (0 if target is None else target.rank)})
            respite_points -= tigers_eye['cost']
            camping_skills.remove(tigers_eye)
            target.buffs.update({'acc_buff': 10})
    if instruction is not None and ((respite_points >= 3 and not stop_on_four)
                                    or ((respite_points == 3 or respite_points >= 7) and stop_on_four)):
        # future - sort party by speed and factor in trinkets (need to update hero class)
        target = next((hero for hero in party if 'acc_buff' not in hero.buffs and (hero.heroClass == 'hellion'
                       or hero.heroClass == 'shieldbreaker' or hero.heroClass == 'highwayman')), None)
        if target is None:
            target = next((hero for hero in party if 'acc_buff' not in hero.buffs
                           and hero.heroClass == 'crusader'), None)
        if target is not None:
            camping_skills_to_use.append({'skill': instruction, 'target': (0 if target is None else target.rank)})
            respite_points -= instruction['cost']
            camping_skills.remove(instruction)
            instruction = None
            target.buffs.update({'acc_buff': 10})
    plague_doctor = next((hero for hero in party if self_medicate is not None
                          and hero.rank == self_medicate['hero_rank']), None)
    if self_medicate is not None and ((respite_points >= 3 and not stop_on_four)
                                      or ((respite_points == 3 or respite_points >= 7) and stop_on_four)) \
            and (plague_doctor.stress > 6 or plague_doctor.OOCPercentHp <= 90) \
            and 'acc_buff' not in plague_doctor.buffs:
        camping_skills_to_use.append({'skill': self_medicate, 'target': 0})
        respite_points -= self_medicate['cost']
        camping_skills.remove(self_medicate)
        plague_doctor.buffs.update({'acc_buff': 10})
    if instruction is not None and ((respite_points >= 3 and not stop_on_four)
                                    or ((respite_points == 3 or respite_points >= 7) and stop_on_four)):
        target = next((hero for hero in party if 'acc_buff' not in hero.buffs
                       and (hero.heroClass == 'man_at_arms' or hero.heroClass == 'houndmaster')), None)
        if target is None:
            target = next((hero for hero in party if 'acc_buff' not in hero.buffs
                           and (hero.heroClass == 'vestal' or hero.heroClass == 'plague_doctor')), None)
        if target is not None:
            camping_skills_to_use.append({'skill': instruction, 'target': (0 if target is None else target.rank)})
            respite_points -= instruction['cost']
            camping_skills.remove(instruction)
            target.buffs.update({'acc_buff': 10})
    if bless is not None and ((respite_points >= 3 and not stop_on_four)
                              or ((respite_points == 3 or respite_points >= 7) and stop_on_four)):
        target = next((hero for hero in party if 'acc_buff' not in hero.buffs and (hero.heroClass == 'hellion'
                       or hero.heroClass == 'shieldbreaker' or hero.heroClass == 'highwayman')), None)
        if target is None:
            target = next((hero for hero in party if 'acc_buff' not in hero.buffs
                           and hero.heroClass == 'crusader'), None)
        if target is None:
            target = next((hero for hero in party if 'acc_buff' not in hero.buffs
                           and (hero.heroClass == 'man_at_arms' or hero.heroClass == 'houndmaster'
                                or hero.heroClass == 'vestal' or hero.heroClass == 'plague_doctor')), None)
        if target is not None:
            camping_skills_to_use.append({'skill': bless, 'target': (0 if target is None else target.rank)})
            respite_points -= bless['cost']
            camping_skills.remove(bless)
            target.buffs.update({'acc_buff': 10})


def select_party_campfire_buffs(camping_skills, camping_skills_to_use):
    print('Select Party Buffs!')
    global respite_points
    # party buffs
    weapons_practice = next((skill for skill in camping_skills if skill['skill_name'] == 'weapons_practice'), None)
    tactics = next((skill for skill in camping_skills if skill['skill_name'] == 'tactics'), None)
    snake_eyes = next((skill for skill in camping_skills if skill['skill_name'] == 'snake_eyes'), None)

    if weapons_practice is not None and respite_points >= 4:
        camping_skills_to_use.append({'skill': weapons_practice, 'target': 0})
        respite_points -= weapons_practice['cost']
        camping_skills.remove(weapons_practice)
    if snake_eyes is not None and respite_points >= 3:
        camping_skills_to_use.append({'skill': snake_eyes, 'target': 0})
        respite_points -= snake_eyes['cost']
        camping_skills.remove(snake_eyes)
    if tactics is not None and respite_points >= 4:
        camping_skills_to_use.append({'skill': tactics, 'target': 0})
        respite_points -= tactics['cost']
        camping_skills.remove(tactics)


def select_tier_2_campfire_buffs(camping_skills, camping_skills_to_use):
    print('Select Tier 2 Buffs!')
    global respite_points
    # offensive_buffs
    sharpen_spear = next((skill for skill in camping_skills if skill['skill_name'] == 'sharpen_spear'), None)
    maintain_equipment = next((skill for skill in camping_skills if skill['skill_name'] == 'maintain_equipment'), None)
    unparalleled_finesse = next((skill for skill in camping_skills if skill['skill_name'] == 'unparalleled_finesse'),
                                None)
    clean_guns = next((skill for skill in camping_skills if skill['skill_name'] == 'clean_guns'), None)

    if clean_guns is not None and respite_points >= 4:
        camping_skills_to_use.append({'skill': clean_guns, 'target': 0})
        respite_points -= clean_guns['cost']
        camping_skills.remove(clean_guns)
    if sharpen_spear is not None and respite_points >= 3:
        camping_skills_to_use.append({'skill': sharpen_spear, 'target': 0})
        respite_points -= sharpen_spear['cost']
        camping_skills.remove(sharpen_spear)
    if unparalleled_finesse is not None and respite_points >= 4:
        camping_skills_to_use.append({'skill': unparalleled_finesse, 'target': 0})
        respite_points -= unparalleled_finesse['cost']
        camping_skills.remove(unparalleled_finesse)
    if maintain_equipment is not None and respite_points >= 4:
        camping_skills_to_use.append({'skill': maintain_equipment, 'target': 0})
        respite_points -= maintain_equipment['cost']
        camping_skills.remove(maintain_equipment)
