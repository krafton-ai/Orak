import re
import time

from .skill_registry import register_skill


@register_skill("mouse_check_do_action")
def mouse_check_do_action(io_env, x, y, duration=0.1):
    """
    Engages with the game element located at the coordinates (x, y) by executing a click using the right mouse button. This function is essential for interacting with objects within the game world, whether it be to open chests, interact with NPCs, or navigate through game menus. The precise execution of the double right-click mimics player actions, offering an automated yet natural interaction within the game environment.
    Note: x and y must be in the scope of the 8 grids around the player.

    Parameters:
     - x: The X-coordinate on the screen representing the horizontal axis where the double right-click is to be performed, directly correlating to the game's graphical interface.
     - y: The Y-coordinate on the screen representing the vertical axis, pinpointing the exact location for the interaction. This ensures that actions are carried out on the intended game element without misplacement or error.
     - duration: The duration for which the right mouse button is held down (default is 0.1 second).
    """
    io_env.mouse_move(x, y)
    time.sleep(0.2)
    io_env.mouse_click_button("right mouse button", duration=duration)


@register_skill("warp_to_shop")
def warp_to_shop(io_env):
    """
    Warp the character to the shop.
    """
    io_env.key_press("g")
    time.sleep(0.5)


# @register_skill("warp_to_farm")
# def warp_to_farm(io_env):
#     """
#     Warp the character to the farm.
#     """
#     io_env.key_press("h")


@register_skill("mouse_use_tool")
def mouse_use_tool(io_env, x, y, duration=0.1):
    """
    Adjusts the player's orientation towards the specified position (x, y) on the screen, then simulates the action of using or interacting with tools in hand or objects within the game or application. This is achieved by moving the mouse to the specified location and performing a single left mouse click.
    Notes:
    1. This function is specifically designed for scenarios in games or applications where direct mouse interactions are necessary to use tools or interact with objects.
    2. A brief delay follows the click action to ensure the intended interaction is properly registered by the game or application.
    3. The parameters x and y must represent positions that are within the 8 adjacent grids surrounding the player, ensuring the action is contextually relevant and possible within the game's mechanics.

    Parameters:
     - x: The X coordinate on the screen to which the mouse will be moved, reflecting the target location for interaction. Coordinates should be within the scope of the 8 grids surrounding the player.
     - y: The Y coordinate on the screen to which the mouse will be moved, reflecting the target location for interaction. Coordinates should be within the scope of the 8 grids surrounding the player.
     - duration: The duration for which the left mouse button is held down (default is 0.1 second).
    """
    io_env.mouse_move(x, y)
    io_env.mouse_click_button("left mouse button", duration=duration)


@register_skill("do_action")
def do_action(io_env):
    """
    The function is designed to perform a generic action on objects or characters within one body length of the player character. This could include planting a seed if a seed is selected, harvesting a plant, interacting with other characters, entering doors, opening boxes, or picking up objects. The action is context-specific and depends on what the player is close to in the game environment. This function is essential for progressing through the game, completing quests, and engaging with various interactive elements in the game world, but is limited to only affecting things in very close proximity to the player character.
    """
    io_env.key_press("x")


@register_skill("use_tool")
def use_tool(io_env):
    """
    Executes an in-game action commonly assigned to using the character's current selected tool. According to the selected tool, this action can range from chopping wood using an axe, digging and til soil using a hoe, watering crops using a watering can, breaking stones using a pickaxe, or cutting grass into hay using a scythe. The use of tools is essential for various activities in the game, such as farming, mining, and combat, making this function a versatile and crucial skill for efficient gameplay.
    """
    io_env.key_press("c")
    time.sleep(0.5)


@register_skill("open_menu")
def open_menu(io_env):
    """
    Opening the menu.
    """
    io_env.key_press("esc")


@register_skill("close_menu")
def close_menu(io_env):
    """
    Closing the menu.
    """
    io_env.key_press("esc")


@register_skill("open_journal")
def open_journal(io_env):
    """
    Opening the journal.
    """
    io_env.key_press("f")


@register_skill("close_journal")
def close_journal(io_env):
    """
    Closing the journal.
    """
    io_env.key_press("f")


@register_skill("open_map")
def open_map(io_env):
    """
    Opening the map.
    """
    io_env.key_press("m")


@register_skill("close_map")
def close_map(io_env):
    """
    Closing the map.
    """
    io_env.key_press("m")


@register_skill("open_chatbox")
def open_chatbox(io_env):
    """
    Opening the chatbox.
    """
    io_env.key_press("t")


@register_skill("close_chatbox")
def close_chatbox(io_env):
    """
    Closing the chatbox.
    """
    io_env.key_press("t")


@register_skill("move_up")
def move_up(io_env, grid=1):
    """
    Moves the character upward (north).

    Parameters:
     - grid: The number of grids the character moves up.
    """
    io_env.key_press("w", grid * 0.18)


@register_skill("move_down")
def move_down(io_env, grid=1):
    """
    Moves the character downward (south).

    Parameters:
     - grid: The number of grids the character moves down.
    """
    io_env.key_press("s", grid * 0.18)


@register_skill("move_left")
def move_left(io_env, grid=1):
    """
    Moves the character left (west).

    Parameters:
     - grid: The number of grids the character moves left.
    """
    io_env.key_press("a", grid * 0.18)


@register_skill("move_right")
def move_right(io_env, grid=0.1):
    """
    Moves the character right (east).

    Parameters:
     - grid: The number of grids the character moves right.
    """
    io_env.key_press("d", grid * 0.18)


@register_skill("select_tool")
def select_tool(io_env, key):
    """
    Selects a specific tool from the in-game toolbar based on the given tool number. Each tool serves a distinct purpose essential for managing your farm and exploring the world. This function allows for the quick selection of tools, crucial for efficient gameplay during various in-game activities such as farming, mining, or combat.
    Note: Ensure the tool number is within the valid range to prevent errors. This function is essential for efficiently managing tool use in various game scenarios, enabling the player to swiftly switch between tools as the situation demands.

    Parameters:
     - key: A key representing the position of the tool in the toolbar. The value must be in ["1","2","3","4","5","6","7","8","9","0","-","+"], inclusive.
    """
    regex_pattern = r"[0-9\-+]"
    if re.match(regex_pattern, str(key)):
        io_env.key_press(str(key))
    else:
        raise ValueError(
            "Invalid key in select_tool. Key must be in the range [0-9,-,+]"
        )


@register_skill("shift_toolbar")
def shift_toolbar(io_env):
    """
    Cycles through the toolbar slots in the game by pressing the "Tab" key. This action allows the player to switch between different sets of tools or items quickly without navigating the inventory screen. Each press of the "Tab" key moves the selection to the next toolbar slot, making it efficient for changing equipment or items during gameplay.
    Note: The number of toolbar slots and the cycle order depend on the game settings and modifications (if any). Ensure to familiarize yourself with the toolbar configuration for optimal use of this skill.
    """
    io_env.key_press("tab")


@register_skill("get_out_of_house")
def get_out_of_house(io_env):
    """
    Move the character out of the house. This function automates the action of moving the character out of the house by navigating through the door. This function only takes effect when the character is inside the house and in bed.
    """
    move_left(io_env, grid=6)
    time.sleep(0.1)
    move_down(io_env, grid=4)
    time.sleep(2)
    move_down(io_env, grid=2)
    time.sleep(0.5)


@register_skill("go_house_and_sleep")
def go_house_and_sleep(io_env):
    """
    Let the character move to house and enter the house and then move the character to the bed and interact with it to go to sleep. This function automates the action of moving the character to the bed and interacting with it to go to sleep.
    """
    # io_env.key_press("p")
    # time.sleep(2)

    # move_up(io_env, grid=2)
    # do_action(io_env)
    # time.sleep(2)

    io_env.key_press("h")  # move to farmhouse 3, 11

    time.sleep(1)
    move_up(io_env, grid=1.5)
    time.sleep(0.1)
    move_right(io_env, grid=7)
    time.sleep(0.5)

    mouse_check_do_action(io_env, 1920, 2000)
    time.sleep(3)
    io_env.key_press("esc")  # to close farming level up popup 
    time.sleep(2)
    io_env.mouse_click_button("right mouse button", duration=0.1)  # update state


@register_skill("buy_item")
def buy_item(io_env, item_name, item_count):
    """
    This function opens the shop interface, selects the specified item, and buys the desired quantity. It can be executed from anywhere in the game world, ensuring seamless item acquisition. If item_name is not one of the available choices, the function will do nothing.
    
    Parameters:
    - item_name: The name of the item to be bought. (CHOICES: "Parsnip Seeds", "Bean Starter", "Cauliflower Seeds", "Potato Seeds")
    - item_count: The number of items to be bought.
    """

    # open shop interface
    io_env.key_press("l")

    time.sleep(0.5)
    if item_name.lower() == "Parsnip Seeds".lower():
        io_env.mouse_move(1920, 800)
    elif item_name.lower() == "Bean Starter".lower():
        io_env.mouse_move(1920, 900)
    elif item_name.lower() == "Cauliflower Seeds".lower():
        io_env.mouse_move(1920, 1000)
    elif item_name.lower() == "Potato Seeds".lower():
        io_env.mouse_move(1920, 1100)
    else:
        # exit the shop interface
        io_env.key_press("r")
        time.sleep(1)
        return

    time.sleep(0.5)
    for i in range(item_count):
        io_env.mouse_click_button("left mouse button", duration=0.1)
        time.sleep(0.5)

    # esc to cancel item selection (if enough money) or exit the shop interface (if not enough money)
    io_env.key_press("esc")
    time.sleep(1)
    # r to exit the shop interface
    io_env.key_press("r")
    time.sleep(1)

@register_skill("sell_item")
def sell_item(io_env):
    """
    Sell all crops in the inventory. This function automatically opens the shop interface and sells all crops in the inventory. This function operates wherever the player is in the game world.
    """

    io_env.key_press("k")

@register_skill("till_soil")
def till_soil(io_env, num_tiles):
    """
    Till the soil. This function automatically till the given number of soil tiles located at the predefined position. This function only work when the character is in the farm area.
    
    Parameters:
    - num_tiles: Number of soil tiles to till.
    """

    io_env.key_press("j")
    
@register_skill("plant_seeds")
def plant_seeds(io_env):
    """
    This function plants all available seeds from the inventory into tilled soil. It operates under the assumption that there is a sufficient number of empty tilled soil plots. If there are fewer available plots than seeds, only the available plots will be used. The character must be in the farm area for this function to work. If no seeds are in the inventory, the function will do nothing.
    """

    io_env.key_press("o")
    
@register_skill("water_seeds")
def water_seeds(io_env):
    """
    This function waters all planted seeds. This function only work when the character is in the farm area. If all plants are watered, this function will do nothing.
    """

    io_env.key_press("i")

@register_skill("harvest_crops")
def harvest_crops(io_env):
    """
    Harvest all crops which are ready to harvest. This function only work when the character is in the farm area.
    """

    io_env.key_press("u")


__all__ = [
    # "mouse_check_do_action",
    # "mouse_use_tool",
    "do_action",
    "use_tool",
    # "access_setting",
    "open_menu",
    "close_menu",
    "open_journal",
    "close_journal",
    "open_map",
    "close_map",
    # "open_chatbox",
    # "close_chatbox",
    "move_up",
    "move_down",
    "move_left",
    "move_right",
    # "move",
    # "walk",
    "select_tool",
    # "shift_toolbar"
]
