import time
import re
import heapq
from mcp_game_servers.pokemon_red.game.utils.map_utils import *

def execute_action_response(toolset, action_response: str):
    try:
        inside = action_response[len("use_tool("):-1]
        tool_name, arg_str = inside.split(",", 1)
        tool_name = tool_name.strip()
        arg_str = arg_str.strip().lstrip("(").rstrip(")")
        kwargs = dict(eval(f"dict({arg_str})"))

        # Execute functions in toolset
        method = getattr(toolset, tool_name)
        return method(**kwargs)

    except Exception as e:
        print(f"[execute_tool error] {e}")
        return f"[execute_tool error] {e}"
    

# Pokemon specific
def process_state_tool(env, toolset, map_memory_dict, step_count, dialog_buffer, text_obs):
    state_dict = env.parse_game_state(text_obs)
    map_memory_dict = toolset.get_map_memory_dict(state_dict, map_memory_dict)
    current_map = state_dict['map_info']['map_name']

    step_count += 1

    if dialog_buffer != []:
        text_obs = replace_filtered_screen_text(text_obs, dialog_buffer)
        dialog_buffer = []

    # if self.state_dict['state'] != 'Title' and current_map in self.map_memory_dict.keys():
    if state_dict['state'] == 'Field' and current_map in map_memory_dict.keys():
        text_obs = replace_map_on_screen_with_full_map(text_obs, map_memory_dict[current_map]["explored_map"])

    return text_obs, state_dict, map_memory_dict, step_count, dialog_buffer

class PokemonToolset:
    def __init__(self, agent):
        """
        Toolset has access to the agent and its state/memory.
        You can access map_memory_dict, state_dict, etc. via self.agent.
        """
        self.agent = agent

    def get_map_memory_dict(self, state_dict, map_memory_dict):
        current_map = state_dict['map_info']['map_name']
        if not state_dict['map_info']['x_max'] == None:
            if not current_map in map_memory_dict.keys():
                map_memory_dict[current_map] = {
                    "explored_map": construct_init_map(
                        state_dict['map_info']['x_max'],
                        state_dict['map_info']['y_max'],
                        state_dict['map_info']['map_screen_raw']
                        ),
                    "history": [],
                }
            else:
                map_memory_dict[current_map]["explored_map"] = refine_current_map(
                    map_memory_dict[current_map]["explored_map"],
                    state_dict['map_info']['x_max'],
                    state_dict['map_info']['y_max'],
                    state_dict['map_info']['map_screen_raw']
                    )
        return map_memory_dict
        
    def _get_current_state(self):
        current_state = self.agent.env._receive_state()
        self.agent.memory.state_dict = self.agent.env.parse_game_state(current_state)
        self.agent.memory.map_memory_dict = self.get_map_memory_dict(self.agent.memory.state_dict, self.agent.memory.map_memory_dict)
        return self.agent.memory.state_dict

    def _reconstruct_directions(self, parent, x_start, y_start, x_dest, y_dest):
        """
        Trace back the path from (x_start, y_start) to (x_dest, y_dest) and return as a string like "up | right | ..."
        """
        path = []
        cur = (x_dest, y_dest)

        while cur != (x_start, y_start):
            prev = parent[cur]
            dx = cur[0] - prev[0]
            dy = cur[1] - prev[1]

            # Jumping over a ledge is also treated as a one-tile movement
            if dx > 0:
                path.append("right")
            elif dx < 0:
                path.append("left")
            elif dy > 0:
                path.append("down")
            elif dy < 0:
                path.append("up")

            cur = prev

        path.reverse()
        return " | ".join(path)

    def _find_path_inner(self, x_dest, y_dest, isSurf=False):
        """
        Find a path to the target coordinate and return direction sequence.
        """
        # agent state, map access
        current_map_id = self.agent.memory.state_dict['map_info']['map_name']
        explored_map = self.agent.memory.map_memory_dict[current_map_id]["explored_map"]
        x_player = self.agent.memory.state_dict['map_info']["player_pos_x"]
        y_player = self.agent.memory.state_dict['map_info']["player_pos_y"]
        
        max_y = len(explored_map)
        max_x = len(explored_map[0])

        def in_bounds(x, y):
            return (0 <= x < max_x) and (0 <= y < max_y)

        def can_land(x, y, is_destination=False):
            """
            - 'WarpPoint' is only allowed when it is the destination
            - '~' is only accessible if isSurf=True
            - 'C' is not walkable
            """
            if not in_bounds(x, y):
                return False
            tile = explored_map[y][x]

            if tile in {'O', 'G'}:
                return True
            if tile == '~' and isSurf:
                return True
            if tile == 'WarpPoint' and is_destination:
                return True
            
            return False
        
        if not can_land(x_dest, y_dest, is_destination=True):
            return (False, f"Destination coordinate is not walkable ('{explored_map[y_dest][x_dest]}'). Please reset the destination.")

        def can_jump_ledge(x_ledge, y_ledge, dx, dy, is_destination=False):
            """
            If it's possible to jump over ledge (D/L/R), return the landing coordinate (x2, y2)
            """
            tile = explored_map[y_ledge][x_ledge]
            if tile == 'D':
                # 'D' is only passable when jumping from top to bottom (dy=1, dx=0)
                if dx == 0 and dy == 1:
                    x2, y2 = x_ledge, y_ledge + 1
                    if can_land(x2, y2, is_destination):
                        return (x2, y2)
            elif tile == 'L':
                # 'L' is only passable when jumping from right to left (dx=-1, dy=0)
                if dx == -1 and dy == 0:
                    x2, y2 = x_ledge - 1, y_ledge
                    if can_land(x2, y2, is_destination):
                        return (x2, y2)
            elif tile == 'R':
                # 'R' is only passable when jumping from left to right (dx=1, dy=0)
                if dx == 1 and dy == 0:
                    x2, y2 = x_ledge + 1, y_ledge
                    if can_land(x2, y2, is_destination):
                        return (x2, y2)
            return None

        def heuristic(cx, cy):
            # Manhattan distance
            return abs(cx - x_dest) + abs(cy - y_dest)

        heap = []
        heapq.heappush(heap, (heuristic(x_player, y_player), 0, x_player, y_player))

        came_from = {} 
        g_score = {(x_player, y_player): 0}

        while heap:
            _, cost_g, cx, cy = heapq.heappop(heap)

            # Destination reached
            if (cx, cy) == (x_dest, y_dest):
                return (True, self._reconstruct_directions(came_from, x_player, y_player, x_dest, y_dest))

            # 4 directions
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                nx, ny = cx + dx, cy + dy
                is_dest = ((nx, ny) == (x_dest, y_dest))

                if in_bounds(nx, ny):
                    tile_next = explored_map[ny][nx]
                    # Check if the next tile is walkable
                    if tile_next in {'O', 'G', '~', 'WarpPoint', 'D', 'L', 'R'}:
                        if tile_next in {'D','L','R'}:
                            # Jumping over ledge
                            jump = can_jump_ledge(nx, ny, dx, dy, is_dest)
                            if jump is not None:
                                nx2, ny2 = jump
                                new_g = cost_g + 1
                                if (nx2, ny2) not in g_score or new_g < g_score[(nx2, ny2)]:
                                    g_score[(nx2, ny2)] = new_g
                                    f_score = new_g + heuristic(nx2, ny2)
                                    heapq.heappush(heap, (f_score, new_g, nx2, ny2))
                                    came_from[(nx2, ny2)] = (cx, cy)
                        else:
                            # Normal tile
                            if can_land(nx, ny, is_dest):
                                new_g = cost_g + 1
                                if (nx, ny) not in g_score or new_g < g_score[(nx, ny)]:
                                    g_score[(nx, ny)] = new_g
                                    f_score = new_g + heuristic(nx, ny)
                                    heapq.heappush(heap, (f_score, new_g, nx, ny))
                                    came_from[(nx, ny)] = (cx, cy)

        return (False, "No valid path to the destination currently. Reveal other '?' tiles first, then find a possible route.")
    
    def _nudge_around_and_return(self, x, y, delay=0.3):
        """
        If the player is already at (x, y), move one step to an adjacent walkable tile and return.
        Useful for triggering warp points or resetting state.
        """
        explored_map = self.agent.memory.map_memory_dict[self.agent.memory.state_dict['map_info']['map_name']]["explored_map"]
        max_y = len(explored_map)
        max_x = len(explored_map[0])

        def in_bounds(x, y):
            return 0 <= x < max_x and 0 <= y < max_y

        adjacent_moves = {
            (0, -1): 'up',
            (0, 1): 'down',
            (-1, 0): 'left',
            (1, 0): 'right'
        }

        for (dx, dy), move_cmd in adjacent_moves.items():
            nx, ny = x + dx, y + dy
            if in_bounds(nx, ny) and explored_map[ny][nx] in {'O', 'G', '~'}:
                self.agent.env.send_action_set([move_cmd])
                time.sleep(delay)
                reverse_cmd = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}[move_cmd]
                self.agent.env.send_action_set([reverse_cmd])
                time.sleep(delay)
                return True
        return False

    def _start_interact_inner(self, object_name, isSurf=False):
        """
        Return a direction sequence to move near and interact with the object.
        """
        current_map_id = self.agent.memory.state_dict['map_info']['map_name']
        explored_map = self.agent.memory.map_memory_dict[current_map_id]["explored_map"]

        max_y = len(explored_map)
        max_x = len(explored_map[0])
        
        def find_object_coordinates(explored_map, object_name):
            for y, row in enumerate(explored_map):
                for x, cell in enumerate(row):
                    if cell == object_name:
                        return (x, y)
            return None

        def in_bounds(x, y):
            return (0 <= x < max_x) and (0 <= y < max_y)

        def can_land_for_interaction(x, y):
            """
            Check if the player can stand on the tile during interaction.
            (Same logic as for intermediate path or destination tiles)
            """

            if not in_bounds(x, y):
                return False
            tile = explored_map[y][x]
            if tile in {'O', 'G'}:
                return True
            if tile == '~' and isSurf:
                return True
            if tile == 'WarpPoint':
                return True
            return False

        coord_obj = find_object_coordinates(explored_map, object_name)
        if coord_obj is None:
            return (False, f"{object_name} is not found. Try exploring the map first, or refer to the full map data to identify the correct object name.")
        x_obj, y_obj = coord_obj

        directions = [(0,1),(0,-1),(1,0),(-1,0)]
        stand_candidates = []
        for dx, dy in directions:
            adjx = x_obj + dx
            adjy = y_obj + dy
            if in_bounds(adjx, adjy):
                tile = explored_map[adjy][adjx]
                if tile == 'C':
                    # If it's 'C', step back one more tile
                    bx = adjx + dx
                    by = adjy + dy
                    if can_land_for_interaction(bx, by):
                        stand_candidates.append((bx, by))
                else:
                    # Normally adjacent tiles
                    if can_land_for_interaction(adjx, adjy):
                        stand_candidates.append((adjx, adjy))

        candidates_info = []

        def get_direction_priority(direction):
            if direction == "up":
                return 1
            elif direction == "left":
                return 2
            else:
                return 3

        for (tx, ty) in stand_candidates:
            success, path_str = self._find_path_inner(tx, ty, isSurf)
            if success:
                # Path length
                steps_count = 1 + path_str.count("|")

                dx = x_obj - tx
                dy = y_obj - ty

                # Diagonal positions are not valid for interaction
                if dx != 0 and dy != 0:
                    continue

                if dx > 0 and dy == 0:
                    facing = "right"
                elif dx < 0 and dy == 0:
                    facing = "left"
                elif dx == 0 and dy > 0:
                    facing = "down"
                elif dx == 0 and dy < 0:
                    facing = "up"
                else:
                    # Just in case (dx,dy) = (0,0), meaning the same location?
                    continue

                priority = get_direction_priority(facing)
                candidates_info.append((priority, steps_count, path_str, facing, (tx, ty)))

        if not candidates_info:
            return (False, "No valid path to the destination currently. Reveal other '?' tiles first, then find a possible route.")

        candidates_info.sort(key=lambda x: (x[0], x[1]))

        # Optimal candidate (shortest path and best direction priority)
        best_path_length, best_priority, best_path_str, best_facing, best_coord = candidates_info[0]

        # Return in the form 'path | direction | a'
        if best_path_str == '':
            return (True ,(best_coord, f"{best_facing} | a"))
        return (True, (best_coord, best_path_str + f" | {best_facing} | a"))

    def interact_with_object(self, object_name, isSurf=False, max_attempts=10):
        """
        Try to interact with the object. If it moves away during execution,
        recompute path and retry until success or max_attempts reached.
        """
        if self.agent.memory.state_dict['state'] != 'Field':
            return (False, f"Current state: '{self.agent.memory.state_dict['state']}' state, not 'Field' state")
        if object_name == 'WarpPoint':
            return (False, f"'WarpPoint' cannot be the target of this tool. Use `warp_with_warp_point` tool.")

        for attempt in range(max_attempts):
            success, results = self._start_interact_inner(object_name, isSurf)
            if success:
                target_coord, actions = results
            else:
                return (False, f"{results}")
            commands = re.split(r'[|/;, \t\n]+', actions)

            if len(commands) < 2: return (False, f"Something wents wrong.")

            commands1, commands2 = commands[:-2], commands[-2:]
            if commands1 == [] or commands1 == None:
                pass
            else:
                for action in commands1:
                    self.agent.env.send_action_set([action])
                    time.sleep(0.3)
                    state_dict = self._get_current_state()
                    if state_dict['state'] != 'Field':
                        return (False, f"Interrupted! Current state: '{state_dict['state']}' state, not 'Field' state")

            state_dict = self.agent.memory.state_dict
            if state_dict['state'] != 'Field':
                return (False, f"Interrupted! Current state: '{state_dict['state']}' state, not 'Field' state")
                
            self.agent.env.send_action_set(commands2)
            time.sleep(0.1)

            state_dict = self._get_current_state()
            x_player = state_dict['map_info']["player_pos_x"]
            y_player = state_dict['map_info']["player_pos_y"]
            if state_dict["state"] == 'Dialog' and (x_player, y_player) == target_coord:
                self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
                time.sleep(1.0)
                success, _ = self.continue_dialog()
                if success:
                    return (True, f"Successfully Interact with {object_name}.")
                else:
                    return (False, f"Successfully started interaction with {object_name} but continuing dialog was failed.")
            elif state_dict["state"] == 'Dialog' and (x_player, y_player) != target_coord:
                return (False, "Interrupt by Someone's Dialog.")
            elif 'Battle' in state_dict["state"]:
                return (False, "Interrupt by Battle")
        return (False, f"Unable to interact with {object_name} after {max_attempts} attempts.")
    
    def move_to(self, x_dest, y_dest, isSurf=False, max_attempts=3):
        if self.agent.memory.state_dict['state'] != 'Field':
            return (False, f"'{self.agent.memory.state_dict['state']}' state, not 'Field' state")
        prev_map = self.agent.memory.state_dict['map_info']['map_name']
        explored_map = self.agent.memory.map_memory_dict[prev_map]["explored_map"]
        target_coord = (x_dest, y_dest)
        x_player = self.agent.memory.state_dict['map_info']["player_pos_x"]
        y_player = self.agent.memory.state_dict['map_info']["player_pos_y"]
        if explored_map[y_dest][x_dest] == 'WarpPoint':
            return (False, f"The destination is 'WarpPoint'. Use 'warp_with_warp_point' tool.")
        elif (x_dest, y_dest) == (x_player, y_player):
            return (False, f"The destination is the current position. Set another destination.")

        for attempt in range(max_attempts):
            success, actions = self._find_path_inner(x_dest, y_dest, isSurf)
            if not success:
                return (success, f"{actions}")
            commands = re.split(r'[|/;, \t\n]+', actions)

            if commands is None or commands == [] or commands == ['']:
                return (False, f"The destination is already your position")
            for action in commands:
                self.agent.env._send_action(action)
                time.sleep(0.3)
                self._get_current_state()
                if self.agent.memory.state_dict['state'] != 'Field':
                    return (False, f"Interrupted! Current state: '{self.agent.memory.state_dict['state']}' state, not 'Field' state")
            time.sleep(0.1)

            state_dict = self.agent.memory.state_dict
            if state_dict['state'] != 'Field':
                return (False, f"Cannot move the position. Currently in {state_dict['state']} state.")
            x_player = state_dict['map_info']["player_pos_x"]
            y_player = state_dict['map_info']["player_pos_y"]

            if (x_player, y_player) == target_coord:
                return (True, f"Successfully Move to ({x_dest}, {y_dest}).")
            elif state_dict["state"] == 'Dialog':
                return (False, f"Interrupt by Someone's Dialog before you move to ({x_dest}, {y_dest}).")
            elif 'Battle' in state_dict["state"]:
                return (False, "Interrupt by Battle.")
        return (False, f"Unable to move to ({x_dest}, {y_dest}) after {max_attempts} attempts.")
    
    def warp_with_warp_point(self, x_dest, y_dest, max_attempts=3):
        if self.agent.memory.state_dict['state'] != 'Field':
            return (False, f"Current state: '{self.agent.memory.state_dict['state']}' state, not 'Field' state")
        prev_map = self.agent.memory.state_dict['map_info']['map_name']
        explored_map = self.agent.memory.map_memory_dict[prev_map]["explored_map"]
        
        if not explored_map[y_dest][x_dest] == 'WarpPoint':
            return (False, f"({x_dest}, {y_dest}) is not 'WarpPoint'")
        
        for attempt in range(max_attempts):
            if self.agent.memory.state_dict['state'] != 'Field':
                return (False, f"Cannot move the position. Currently in {self.agent.memory.state_dict['state']} state.")
            
            player_x = self.agent.memory.state_dict['map_info']["player_pos_x"]
            player_y = self.agent.memory.state_dict['map_info']["player_pos_y"]
            if (player_x, player_y) == (x_dest, y_dest):
                x1, y1, map1 = self.agent.env.runner.get_player_pos()
                self._nudge_around_and_return(x_dest, y_dest)
                x2, y2, map2 = self.agent.env.runner.get_player_pos()
            else:
                success, actions = self._find_path_inner(x_dest, y_dest)
                if not success:
                    return (success, f"{actions}")

                commands = re.split(r'[|/;, \t\n]+', actions)

                self.agent.env.send_action_set(commands[:-1])
                x1, y1, map1 = self.agent.env.runner.get_player_pos()
                time.sleep(0.1)
                
                self.agent.env.send_action_set(commands[-1:])
                x2, y2, map2 = self.agent.env.runner.get_player_pos()

                time.sleep(0.1)

            warp_cond1 = abs(x1 - x2) > 1 or abs(y1 - y2) > 1
            warp_cond2 = (map1 != map2)
            warp_cond = warp_cond1 or warp_cond2

            state_dict = self._get_current_state()
            current_map = self.agent.memory.state_dict['map_info']['map_name']

            if warp_cond:
                return (True, f"Success to warp to {current_map} ({x2}, {y2}) using a warp point ({x_dest}, {y_dest}) in {prev_map}")
            elif state_dict["state"] == 'Dialog':
                return (False, f"Interrupt by Someone's Dialog before you move to a warp point ({x_dest}, {y_dest}).")
            elif 'Battle' in state_dict["state"]:
                return (False, "Interrupt by Battle.")
            else:
                # Check if it's a boundary
                player_x = state_dict['map_info']["player_pos_x"]
                player_y = state_dict['map_info']["player_pos_y"]
                x_max = state_dict['map_info']['x_max']
                y_max = state_dict['map_info']['y_max']

                direction = None
                if player_y == 0:
                    direction = 'up'
                elif player_y == y_max:
                    direction = 'down'
                elif player_x == 0:
                    direction = 'left'
                elif player_x == x_max:
                    direction = 'right'

                if direction:
                    # Try moving one more step
                    self.agent.env.send_action_set([direction])
                    time.sleep(0.5)

                    # Check the state again
                    state_dict = self._get_current_state()
                    current_map = self.agent.memory.state_dict['map_info']['map_name']
                    x2, y2, map2 = self.agent.env.runner.get_player_pos()

                    if prev_map != current_map:
                        return (True, f"Success to warp to {current_map} ({x2}, {y2}) using a warp point ({x_dest}, {y_dest}) in {prev_map} (via boundary move)")
        return (False, f"Unable to warp after {max_attempts} attempts.")
        

    def overworld_map_transition(self, direction='north', max_attempts=3):
        if self.agent.memory.state_dict['state'] != 'Field':
            return (False, f"Current state: '{self.agent.memory.state_dict['state']}' state, not 'Field' state")
        map_info = self.agent.memory.state_dict['map_info']
        if map_info['map_type'] != 'overworld':
            return (False, "Map type is not 'overworld'")

        # Check if the map can be expanded in the given direction
        expansion_direction = map_info['expansion_direction']
        expansion_direction = expansion_direction.strip('\'"')
        tokens = re.split(r'[|,/;\s]+', expansion_direction)
        expansion_direction_list = [token.lower() for token in tokens if token.strip()]

        if direction not in expansion_direction_list:
            return (False, f"{direction} is not a valid direction")

        x_max = map_info['x_max']
        y_max = map_info['y_max']

        # TODO: '~' will be added after the 'SURF'
        walkable_tiles = {'O', 'G', 'WarpPoint'}  # Walkable tiles

        # for attempt in range(max_attempts):
        prev_map = self.agent.memory.state_dict['map_info']['map_name']
        explored_map = self.agent.memory.map_memory_dict[prev_map]['explored_map']

        for attempt in range(max_attempts):
            if self.agent.memory.state_dict['state'] != 'Field':
                return (False, f"Cannot move the position. Currently in {self.agent.memory.state_dict['state']} state.")
            
            if direction == 'north':
                candidates = [(x, 0) for x in range(x_max) if explored_map[0][x] in walkable_tiles]
                post_action = 'up'
            elif direction == 'south':
                candidates = [(x, y_max) for x in range(x_max) if explored_map[y_max][x] in walkable_tiles]
                post_action = 'down'
            elif direction == 'west':
                candidates = [(0, y) for y in range(y_max) if explored_map[y][0] in walkable_tiles]
                post_action = 'left'
            elif direction == 'east':
                candidates = [(x_max, y) for y in range(y_max) if explored_map[y][x_max] in walkable_tiles]
                post_action = 'right'
            else:
                return (False, f"{direction} is not valid direction")

            if len(candidates)==0:
                return (False, f"The {direction} side boundary is fully unknown ('?'). Prioritize uncovering other '?' {direction} boundary tiles first, then retry map transition.")

            for i, (x, y) in enumerate(candidates):
                success, actions = self._find_path_inner(x, y)
                if success:
                    break
                elif i==len(candidates)-1:
                    return (False, f"No valid path to the {direction} boundary. Prioritize uncovering other '?' {direction} boundary tiles first, then retry map transition.")
            if actions == '':
                commands = [post_action]
            else:
                actions += f' | {post_action}'
                commands = re.split(r'[|/;, \t\n]+', actions)

            self.agent.env.send_action_set(commands)
            time.sleep(0.1)

            state_dict = self._get_current_state()
            current_map = self.agent.memory.state_dict['map_info']['map_name']

            if prev_map != current_map:
                return (True, f"Success to warp from {prev_map} to {current_map}")
            elif state_dict["state"] == 'Dialog':
                return (False, f"Interrupt by Someone's Dialog before your transition.")
            elif 'Battle' in state_dict["state"]:
                return (False, "Interrupt by Battle.")
        return (False, f"Unable to warp after {max_attempts} attempts.")
    
    def continue_dialog(self):
        "Continuing dialog until selectable options appear or the dialog is over (go to Field or Battle state)"        
        for _ in range(30):
            self.agent.env.send_action_set(['a'])
            time.sleep(0.5)

            text_obs = self.agent.env._receive_state()
            self.agent.memory.state_dict = self.agent.env.parse_game_state(text_obs)
            self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])

            if self.agent.memory.state_dict['state'] == 'Field':
                return (True, f"Success to finish the dialog and enter {self.agent.memory.state_dict['state']} state")
            elif self.agent.memory.state_dict['selection_box_text'] != "N/A":
                return (True, "Selection box appears")

        return (True, "Still in Dialog State")
            
    def select_move_in_battle(self, move_name, max_attempts=3):
        if not 'Battle' in self.agent.memory.state_dict['state']:
            return (False, f"Current state is {self.agent.memory.state_dict['state']}, not Battle! Don't use this battle tool and directly choose {move_name} through POKéMON menu")
        # select 'FIGHT' option
        for i in range(max_attempts):
            if 'FIGHT' not in self.agent.memory.state_dict['selection_box_text']:
                action_sequence = ['b'] * 4
                self.agent.env.send_action_set(action_sequence)
                time.sleep(0.1)
                self._get_current_state()
                if i==2:
                    return (False, "Something went wrong")
            else:
                break
        self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])

        action_sequence = ['up', 'left', 'a']
        self.agent.env.send_action_set(action_sequence)
        time.sleep(0.1)

        # select [move_name] option
        for _ in range(30):
            state_dict = self._get_current_state()
            
            options = state_dict['selection_box_text'].split('\n')
            cursor_row = -1
            move_row = -1
            for row_idx, row in enumerate(options):
                if "▶" in row:
                    cursor_row = row_idx
                if move_name in row:
                    move_row = row_idx
                if cursor_row != -1 and move_row != -1:
                    break
            if move_row == -1:
                return (False, f"No {move_name} in this options")
            if cursor_row == move_row:
                action = 'a'
                break
            elif cursor_row < move_row:
                action = 'down'
            else:
                action = 'up'
            self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
            self.agent.env.send_action_set([action])
            time.sleep(0.1)
        
        self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
        self.agent.env.send_action_set([action])
        time.sleep(1.0)

        # continue dialog
        self._get_current_state()
        success, _ = self.continue_dialog()
        if success:
            return (True, f"Successfully used {move_name}")

    def switch_pkmn_in_battle(self, pokemon_name, max_attempts=3):
        if not 'Battle' in self.agent.memory.state_dict['state']:
            return (False, f"Current state is {self.agent.memory.state_dict['state']}, not Battle! Don't use this battle tool and directly access to POKéMON menu")
        
        # select '<Pk><Mn>' option
        for i in range(max_attempts):
            if 'FIGHT' not in self.agent.memory.state_dict['selection_box_text']:
                action_sequence = ['b'] * 4
                self.agent.env.send_action_set(action_sequence)
                time.sleep(0.1)
                self._get_current_state()
                if i==2:
                    return (False, "Something went wrong")
            else:
                break
        self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])

        action_sequence = ['up', 'right', 'a']
        self.agent.env.send_action_set(action_sequence)
        time.sleep(0.1)
        
        # select [pokemon_name] option
        for _ in range(30):
            state_dict = self._get_current_state()
            
            options = state_dict['filtered_screen_text'].split('\n')
            cursor_row = -1
            name_row = -1
            for row_idx, row in enumerate(options):
                if "▶" in row:
                    cursor_row = row_idx - 1
                if pokemon_name in row:
                    name_row = row_idx
                if cursor_row != -1 and name_row != -1:
                    break
            if name_row == -1:
                return (False, f"No {pokemon_name} in this options")
            if cursor_row == name_row:
                action = 'a'
                break
            elif cursor_row < name_row:
                action = 'down'
            else:
                action = 'up'
            self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
            self.agent.env.send_action_set([action])
            time.sleep(0.1)
        
        self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
        self.agent.env.send_action_set([action])
        time.sleep(0.1)

        # select [SWITCH] option
        self._get_current_state()
        self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
        self.agent.env.send_action_set(['a'])
        time.sleep(1.0)

        # continue dialog
        self._get_current_state()
        success, _ = self.continue_dialog()
        if success:
            return (True, f"Successfully switched to {pokemon_name}")

    def run_away(self, max_attempts=3):
        # select 'RUN' option
        for i in range(max_attempts):
            if 'FIGHT' not in self.agent.memory.state_dict['selection_box_text']:
                action_sequence = ['b'] * 4
                self.agent.env.send_action_set(action_sequence)
                time.sleep(0.1)

                self._get_current_state()
                if i==2:
                    return (False, "Something went wrong")
            else:
                break
        self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])

        action_sequence = ['down', 'right', 'a']
        self.agent.env.send_action_set(action_sequence)
        time.sleep(1.0)
        
        # continue dialog
        self._get_current_state()
        success, _ = self.continue_dialog()
        if success:
            return (True, f"Successfully run!")

    def use_item_in_battle(self, item_name, pokemon_name=None, max_attempts=3):
        # Check if item_name is in the bag
        if not item_name in self.agent.memory.state_dict['inventory']:
            return (False, f"No {item_name} in your bag.")
        
        if not 'Battle' in self.agent.memory.state_dict['state']:
            return (False, f"Current state is {self.agent.memory.state_dict['state']}, not Battle! Don't use this battle tool and directly access to ITEM menu")
        
        # select 'ITEM' option
        for i in range(max_attempts):
            if 'FIGHT' not in self.agent.memory.state_dict['selection_box_text']:
                action_sequence = ['b'] * 4
                self.agent.env.send_action_set(action_sequence)
                time.sleep(0.1)
                
                self._get_current_state()
                if i==2:
                    return (False, "Something went wrong")
            else:
                break
        self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])

        action_sequence = ['down', 'left', 'a']
        self.agent.env.send_action_set(action_sequence)
        time.sleep(0.1)
        
        bag_state = self.agent.memory.state_dict['inventory'].split('\n')
        for i, item_info in enumerate(bag_state):
            if item_name in item_info:
                break
        query_item_idx = i

        # Move cursor to [item_name] and select it
        for _ in range(30):
            # Current cursor item position
            state_dict = self._get_current_state()
            options = state_dict['selection_box_text'].split('\n')
            for row in options:
                if "▶" in row:
                    break
            current_option = row[1:]

            for i, item_info in enumerate(bag_state):
                if current_option in item_info:
                    break
            current_item_idx = i
            if query_item_idx == current_item_idx:
                action = 'a'
                break
            elif query_item_idx < current_item_idx:
                action = 'up'
            else:
                action = 'down'
                
            self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
            
            self.agent.env.send_action_set([action])
            time.sleep(0.1)
        
        self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])

        self.agent.env.send_action_set([action])
        time.sleep(0.1)
        
        # If 'Use item on which' detected, select [pokemon_name]
        if 'Use item on which' in self.state_dict['filtered_screen_text'] and pokemon_name is None:
            return (False, f"You have to select a specific Pokemon.")
        elif 'Use item on which' in self.state_dict['filtered_screen_text'] and pokemon_name is not None:
            for _ in range(30):
                state_dict = self._get_current_state()
                
                options = state_dict['filtered_screen_text'].split('\n')
                cursor_row = -1
                name_row = -1
                for row_idx, row in enumerate(options):
                    if "▶" in row:
                        cursor_row = row_idx - 1
                    if pokemon_name in row:
                        name_row = row_idx
                    if cursor_row != -1 and name_row != -1:
                        break
                if name_row == -1:
                    return (False, f"No {pokemon_name} in this options")
                if cursor_row == name_row:
                    action = 'a'
                    break
                elif cursor_row < name_row:
                    action = 'down'
                else:
                    action = 'up'
                self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
                
                self.agent.env.send_action_set([action])
                time.sleep(0.1)
            
            self.agent.memory.dialog_buffer.append(self.agent.memory.state_dict['filtered_screen_text'])
            
            self.agent.env.send_action_set([action])
            time.sleep(1.0)
        
        self._get_current_state()
        success, _ = self.continue_dialog()
        if success:
            return (True, f"Successfully used {item_name}")

