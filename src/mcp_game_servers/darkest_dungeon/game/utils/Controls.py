import pydirectinput
import time

pydirectinput.FAILSAFE = True


class Controller:
    def __init__(self, debug):
        self.up = 'w' if not debug else ''
        self.down = 's' if not debug else ''
        self.left = 'a' if not debug else ''
        self.right = 'd' if not debug else ''
        self.space = 'space' if not debug else ''
        self.one = '1' if not debug else ''
        self.two = '2' if not debug else ''
        self.three = '3' if not debug else ''
        self.four = '4' if not debug else ''
        self.five = '5' if not debug else ''
        self.torch = 't' if not debug else ''
        self.map = 'm' if not debug else ''
        self.enter = 'enter' if not debug else ''
        self.esc = 'esc' if not debug else ''

        self.left_bumper = '9' if not debug else ''
        self.right_bumper = '0' if not debug else ''

        self.right_stick_up = 'p' if not debug else ''
        self.right_stick_down = ';' if not debug else ''
        self.right_stick_left = 'l' if not debug else ''
        self.right_stick_right = '\'' if not debug else ''

        self.d_pad_up = 'y' if not debug else ''
        self.d_pad_down = 'h' if not debug else ''
        self.d_pad_left = 'g' if not debug else ''
        self.d_pad_right = 'j' if not debug else ''

        self.x = 'x' if not debug else ''
        self.y = 'z' if not debug else ''
        self.a = 'v' if not debug else ''
        self.b = 'b' if not debug else ''
        self.back = 'o' if not debug else ''

        self.left_stick_up = 'k' if not debug else ''
        self.left_stick_down = ',' if not debug else ''
        self.left_stick_left = 'n' if not debug else ''
        self.left_stick_right = '.' if not debug else ''

    # wrapper for pydirectinput press method
    @staticmethod
    def press(key, presses=1):
        for i in range(0, presses):
            print(f'press: {key}')
            pydirectinput.write(key)
        pydirectinput.write('')  # do nothing, important to make sure next write goes through
        time.sleep(.3)

    # wrapper for pydirectinput write method
    @staticmethod
    def write(key, presses=1):
        for i in range(0, presses):
            print(f'write: {key}')
            pydirectinput.write(key)
            pydirectinput.write('')  # do nothing, important to make sure next write goes through
            time.sleep(.7)  # 각 입력마다 sleep 적용

    # wrapper for pydirectinput keyDown method
    @staticmethod
    def keyDown(key):
        print(f'keyDown: {key}')
        pydirectinput.keyDown(key)

    # wrapper for pydirectinput keyUp method
    @staticmethod
    def keyUp(key):
        print(f'keyUp: {key}')
        pydirectinput.keyUp(key)


def attack_target(target_index: int, skill_slot: int, debug: bool = False):
    """
    Attack an enemy at target_index (0-based) using a given skill_slot (1-based).
    
    :param target_index: 0-based index of the enemy to attack (e.g., 0 => first enemy).
    :param skill_slot: 1-based index of the hero's skill slot (e.g., 1 => first skill).
    :param debug: If True, certain inputs are printed or skipped for easier debugging.
    """
    # Do nothing if invalid inputs
    if skill_slot < 1 or target_index < 0:
        return

    c = Controller(debug)

    print(f"Attacking target {target_index + 1} using skill slot {skill_slot}")

    # Select Ability
    time.sleep(0.1)
    # Press the skill slot key (if debug=False, actually press; if debug=True, skip)
    c.write(str(skill_slot) if not debug else '', 2)
    # Move cursor left a bit
    c.write(c.left_stick_left, 2)

    # Move Cursor to target
    c.write(c.left_stick_right, target_index)

    # Confirm Attack
    c.write(c.d_pad_right, 2)  
    c.write(c.a, 2)
    print("Attack Target complete!")


def heal_target(target_rank: int, skill_slot: int, debug: bool = False):
    """
    Heal an ally at target_rank (1-based) using a given skill_slot (1-based).
    
    :param target_rank: 1-based position of the ally to heal (1 => front hero, etc.).
    :param skill_slot: 1-based index of the hero's skill slot (1 => first skill).
    :param debug: If True, certain inputs are printed or skipped for easier debugging.
    """
    # Do nothing if invalid inputs
    if skill_slot < 1 or target_rank < 1:
        return

    c = Controller(debug)

    print(f"Healing target at rank {target_rank} using skill slot {skill_slot}")

    # Select Ability
    time.sleep(0.1)
    c.write(str(skill_slot) if not debug else '', 2)

    # Move to the "heal" ability section (hard-coded 4 presses to the right)
    c.write(c.left_stick_right, 4)

    # Move cursor to the target's rank, minus 1 for zero-based movement
    c.write(c.left_stick_left, target_rank - 1)

    # Confirm Heal
    c.write(c.d_pad_right, 2)
    c.write(c.a, 2)
    print("Heal target complete!")


def swap_hero(current_rank: int, swap_distance: int, debug: bool = False):
    """
    Swap the hero's position by moving them forward or backward a certain number of ranks.
    Positive swap_distance => move forward
    Negative swap_distance => move backward
    Zero swap_distance => skip turn

    :param current_rank: The hero's current rank (1..4).
    :param roster_index: The hero's ID in party_order (must exist in party_order).
    :param swap_distance: Number of ranks to move (e.g., +1 => forward one, -2 => back two, 0 => skip).
    :param party_order: A list of roster IDs reflecting the party order (index 0 => front).
    :param debug: If True, certain inputs are printed or skipped for easier debugging.
    """
    # Compute the new rank based on swap_distance
    new_rank = current_rank + (swap_distance * -1)

    # Do nothing if inputs are invalid
    if not (1 <= current_rank <= 4):
        return
    if not (1 <= new_rank <= 4):
        return

    c = Controller(debug)

    print(f"Swap distance: {swap_distance}")
    print("Updating party order...")

    # Select 'Swap' from choices
    time.sleep(0.1)
    c.write(c.five, 2)

    # Move Cursor
    if swap_distance < 0:  # moving backward
        # Convert distance to positive for cursor presses
        dist = abs(swap_distance)
        # This offset logic depends on the hero's current rank
        # (We adjust the cursor to the correct starting position)
        offset = None
        if current_rank == 1:
            offset = -1
        elif current_rank == 2:
            offset = 0
        elif current_rank == 3:
            offset = 1

        if offset is None:
            return  # do nothing if we can't handle the rank offset

        # Move to start, then move left
        c.write(c.left_stick_right, 3)
        c.write(c.left_stick_left, presses=offset + dist)

    elif swap_distance > 0:  # moving forward
        dist = swap_distance
        offset = None
        if current_rank == 4:
            offset = -1
        elif current_rank == 3:
            offset = 0
        elif current_rank == 2:
            offset = 1

        if offset is None:
            return

        # Move to start, then move right
        c.write(c.left_stick_left, 3)
        c.write(c.left_stick_right, presses=offset + dist)

    else:  # swap_distance == 0 => skip turn
        c.write(c.b, 2)
        c.write(c.left_stick_right)

    # Confirm swap (or skip)
    c.write(c.d_pad_right, 2)
    c.write(c.a, 2)
    print("Swap complete!")


def reset_party_order(in_room, debug):
    print('reset_party_order')
    c = Controller(debug)
    if in_room:  # move forward if in room so it doesn't activate curio
        c.keyDown(c.right)
        time.sleep(1.3)
        c.keyUp(c.right)
    c.write(c.map)
    c.write(c.b, 3)
    c.keyDown(c.a)
    time.sleep(2)
    c.keyUp(c.a)
    time.sleep(.5)
    if not in_room:  # move forward before re-reading save file and selecting lead hero in hallway
        c.write(c.right, 3)


def drop_item(item_number, debug):
    print(f'drop_item {item_number}')
    c = Controller(debug)
    offset = None
    c.write(c.left_stick_up, 3)  # make sure cursor is in correct start position
    c.write(c.left_stick_down)

    if item_number < 8:
        offset = item_number
    elif 7 < item_number < 16:
        c.write(c.left_stick_down)
        offset = item_number - 8

    c.write(c.left_stick_right, offset)
    c.write(c.d_pad_left, 2)  # necessary to make sure button press goes through, make sure doesn't open quest log
    # c.write(c.right_stick_down, 2)  # try this instead if still doesn't work, be careful can cause us to leave room
    c.keyDown(c.y)
    time.sleep(1.2)
    c.keyUp(c.y)
    c.write(c.a)


def combine_items(item_number_1, item_number_2, debug, last_slot_trinket=None, selected_hero_class=None):
    print(f'combine_items in inventory, {item_number_1}, {item_number_2}')
    c = Controller(debug)
    c.write(c.left_stick_up, 2)
    c.write(c.left_stick_down)

    if item_number_1 < 8:
        c.write(c.left_stick_right, item_number_1)
        c.write(c.a)
        if last_slot_trinket is not None \
                and ('hero_class' not in last_slot_trinket or last_slot_trinket['hero_class'] == selected_hero_class):
            if item_number_2 < 8:
                c.write(c.left_stick_right, 2)
                c.write(c.left_stick_up)
                c.write(c.left_stick_right, item_number_2)
            elif 7 < item_number_2 < 16:
                c.write(c.left_stick_right, 2)
                c.write(c.left_stick_right, item_number_2 - 8)
        elif item_number_2 < 8:
            if item_number_2 > item_number_1:
                c.write(c.left_stick_right, item_number_2 - item_number_1)
            elif item_number_2 < item_number_1:
                c.write(c.left_stick_left, item_number_1 - item_number_2)
        elif 7 < item_number_2 < 16:
            c.write(c.left_stick_down)
            offset = item_number_2 - 8
            if offset > item_number_1:
                c.write(c.left_stick_right, offset - item_number_1)
            elif offset < item_number_1:
                c.write(c.left_stick_left, item_number_1 - offset)

    elif 7 < item_number_1 < 16:
        c.write(c.left_stick_down)
        offset = item_number_1 - 8
        c.write(c.left_stick_right, offset)
        c.write(c.a)
        if last_slot_trinket is not None \
                and ('hero_class' not in last_slot_trinket or last_slot_trinket['hero_class'] == selected_hero_class):
            if item_number_2 < 8:
                c.write(c.left_stick_right, 2)
                c.write(c.left_stick_up)
                c.write(c.left_stick_right, item_number_2)
            elif 7 < item_number_2 < 16:
                c.write(c.left_stick_right, 2)
                c.write(c.left_stick_right, item_number_2 - 8)
        elif item_number_2 < 8:
            c.write(c.left_stick_up)
            if item_number_2 > offset:
                c.write(c.left_stick_right, item_number_2 - offset)
            elif item_number_2 < offset:
                c.write(c.left_stick_left, offset - item_number_2)
        elif 7 < item_number_2 < 16:
            if item_number_2 > item_number_1:
                c.write(c.left_stick_right, item_number_2 - item_number_1)
            elif item_number_2 < item_number_1:
                c.write(c.left_stick_left, item_number_1 - item_number_2)
    c.write(c.a)


def take_item(index, debug):
    print(f'take_item {index}')
    c = Controller(debug)
    c.write(c.left_stick_down)
    c.write(c.left_stick_up, 2)
    c.write(c.left_stick_right, index)
    c.write(c.a)


def use_item_on_curio(item_number, debug):
    print(f'use_item_on_curio {item_number}')
    c = Controller(debug)
    offset = None
    c.write(c.right_stick_down)
    c.write(c.y)

    if item_number < 8:
        offset = item_number
    elif 7 < item_number < 16:
        c.write(c.left_stick_down)
        offset = item_number - 8

    c.write(c.left_stick_right, offset)
    c.write(c.y)


def use_item(item_number, debug):
    print(f'using item {item_number}')
    c = Controller(debug)
    offset = None
    c.write(c.down)
    c.write(c.d_pad_up)

    if item_number < 8:
        offset = item_number
    elif 7 < item_number < 16:
        c.write(c.left_stick_down)
        offset = item_number - 8

    c.write(c.left_stick_right, offset)
    c.write(c.y)