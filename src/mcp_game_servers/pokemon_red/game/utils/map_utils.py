import re

def construct_init_map(x_max, y_max, map_screen_raw):
    width, height = x_max + 1, y_max + 1

    # 1. Initialize empty map
    maps = [['?' for _ in range(width)] for _ in range(height)]

    # 2. Extract coordinates and symbols from map_screen_raw
    if map_screen_raw:
        map_lines = map_screen_raw.strip().split('\n')
        for line in map_lines:
            tile_matches = re.findall(r"\(\s*(\d+),\s*(\d+)\):\s*([^\s]+)", line)
            for x_str, y_str, val in tile_matches:
                x, y = int(x_str), int(y_str)
                if 0 <= x < width and 0 <= y < height:
                    maps[y][x] = val

    return maps

def refine_current_map(maps, x_max, y_max, map_screen_raw):
    width, height = x_max + 1, y_max + 1

    if map_screen_raw:
        map_lines = map_screen_raw.strip().split('\n')
        sprite_positions = []

        for line in map_lines:
            tile_matches = re.findall(r"\(\s*(\d+),\s*(\d+)\):\s*([^\s]+)", line)
            for x_str, y_str, val in tile_matches:
                x, y = int(x_str), int(y_str)
                if 0 <= x < width and 0 <= y < height:
                    if val.startswith("SPRITE_"):
                        sprite_positions.append((x, y, val))
                    else:
                        maps[y][x] = val

        # Seperately process SPRITEs
        for x, y, sprite_val in sprite_positions:
            for row in range(height):
                for col in range(width):
                    if maps[row][col] == sprite_val and (col != x or row != y):
                        maps[row][col] = '?'
            maps[y][x] = sprite_val

    return maps

def replace_map_on_screen_with_full_map(state_text: str, map_current: list[list[str]]) -> str:
    # Return original text if map_current is empty or invalid
    if not map_current or not isinstance(map_current, list) or \
        not (all(isinstance(row, list) for row in map_current) if map_current else True):
        return state_text
    if map_current and not map_current[0]: # handles case like [[]]
            map_current = [] # Treat as empty map

    # --- 0. Remove "Map on Screen" section first ---
    # Uses the format "Map on Screen:" as per typical game state text
    processed_state_text = re.sub(
        r"Map on Screen:(?:\n(?:\(\s*\d+,\s*\d+\): [^\n]+\n*)+)?", # Allow empty or non-existent section
        "", state_text, flags=re.DOTALL
    )

    # --- Then, fill 'N/A' to other specified empty sections ---
    section_names = [
        "Filtered Screen Text",
        "Selection Box Text",
        "Enemy Pokemon",
        "Current Party",  # Updated
        "Badge List",
        "Bag",            # Updated
        "Current Money"   # Added
    ]
    for section in section_names:
        pattern = rf"(\[{re.escape(section)}\])\n(?=\s*\[|\Z)"
        processed_state_text = re.sub(pattern, r"\1\nN/A\n", processed_state_text, flags=re.MULTILINE)

    # Clean up potentially multiple blank lines left by removals/changes
    processed_state_text = re.sub(r"\n\s*\n", "\n\n", processed_state_text).strip()

    # --- 1. Extract player position ---
    player_x, player_y = -1, -1  # Default if not found
    player_pos_match = re.search(r"Your position \(x, y\): \((\d+), (\d+)\)", processed_state_text)
    if player_pos_match:
        player_x = int(player_pos_match.group(1))
        player_y = int(player_pos_match.group(2))

    # --- 2. Generate the compact full map text ---
    map_grid_lines = []
    notable_objects = {} # Stores {(x, y): "char_representation: full_name"}

    if not map_current: # If map_current became empty (e.g. was [[]] or initially empty)
        full_map_text_block = "[Full Map]\n(Map data is empty or malformed)\n"
    else:
        num_rows = len(map_current)
        num_cols = len(map_current[0])
        if num_cols == 0: # Handle case where rows exist but are empty
                full_map_text_block = "[Full Map]\n(Map data has rows but no columns)\n"
                map_current = [] # Treat as empty for subsequent logic
        else:
            actual_x_max = num_cols - 1
            actual_y_max = num_rows - 1

            # --- Calculate paddings and dimensions ---
            # Width of the y-axis number (e.g., '7' is 1, '10' is 2)
            y_label_num_width = len(str(actual_y_max)) if actual_y_max >= 0 else 1
            # String for the longest y-axis label, e.g., " 7 | " or "10 | "
            # This defines the left padding for header lines.
            max_y_label_str = f"{actual_y_max:<{y_label_num_width}} | "
            header_left_padding = " " * len(max_y_label_str)

            x_axis_markers_prefix = "(x=0) "
            x_axis_markers_suffix = f" (x={actual_x_max})"
            
            # Total width of the content part of the column number line (markers + digits)
            # This width is used for centering (y=0) and (y=Y_MAX) labels.
            column_line_content_width = len(x_axis_markers_prefix) + num_cols + len(x_axis_markers_suffix)

            # --- Map Header Construction ---
            # (y=0) label
            y0_label_text = "(y=0)"
            y0_padding_count = (column_line_content_width - len(y0_label_text)) // 2
            y0_padding = " " * max(0, y0_padding_count)
            map_grid_lines.append(f"{header_left_padding}{y0_padding}{y0_label_text}")

            # Column number headers (units, tens, hundreds)
            col_headers_digits_only_list = [] # Stores just the digit strings, each num_cols long
            if num_cols > 0:
                if num_cols >= 100:
                    col_headers_digits_only_list.append("".join([str(i // 100 % 10) if i >= 100 else ' ' for i in range(num_cols)]))
                if num_cols >= 10:
                    col_headers_digits_only_list.append("".join([str(i // 10 % 10) if i >= 10 else ' ' for i in range(num_cols)]))
                col_headers_digits_only_list.append("".join([str(i % 10) for i in range(num_cols)])) # Units

            for i, digits_str in enumerate(col_headers_digits_only_list):
                if i == len(col_headers_digits_only_list) - 1: # Unit digits line (last in list) gets x-axis markers
                    line_content = f"{x_axis_markers_prefix}{digits_str}{x_axis_markers_suffix}"
                else: # Tens, Hundreds lines: pad to align digits under markers
                    line_content = f"{' ' * len(x_axis_markers_prefix)}{digits_str}{' ' * len(x_axis_markers_suffix)}"
                map_grid_lines.append(f"{header_left_padding}{line_content}")
            
            # Separator line: +--------+
            # Aligns with the num_cols part of the header
            separator_padding = " " * (len(header_left_padding) + len(x_axis_markers_prefix))
            map_grid_lines.append(f"{separator_padding}+{'-' * num_cols}+")

            # --- Map Rows Construction ---
            for y_coord in range(num_rows):
                current_y_label_str = f"{y_coord:<{y_label_num_width}} | " # e.g., "0 | ", "10| "
                line_content_chars = []
                for x_coord in range(num_cols):
                    val_at_cell = map_current[y_coord][x_coord]
                    original_char_code = '?' # Default representation

                    if val_at_cell and isinstance(val_at_cell, str):
                        if len(val_at_cell) == 1:
                            original_char_code = val_at_cell
                        else:
                            original_char_code = val_at_cell[0].upper()
                            notable_objects[(x_coord, y_coord)] = f"{val_at_cell}"
                    elif val_at_cell is None or val_at_cell == "":
                        original_char_code = '?'
                    else:
                        original_char_code = 'E' # Error for unexpected type
                        notable_objects[(x_coord, y_coord)] = f"E: Invalid_Data_Type({type(val_at_cell).__name__})"
                    
                    # Player position overrides other characters on the grid
                    # if x_coord == player_x and y_coord == player_y:
                    #     char_for_grid = 'P'
                    # else:
                    #     char_for_grid = original_char_code
                    # line_content_chars.append(char_for_grid)
                    line_content_chars.append(original_char_code)
                
                map_row_content_str = "".join(line_content_chars)
                # Map content directly follows y-axis label for compactness
                map_grid_lines.append(f"{current_y_label_str}{map_row_content_str}")

            # --- Map Footer Construction ---
            # (y=y_max) label, centered like (y=0)
            y_max_label_text = f"(y={actual_y_max})"
            y_max_padding_count = (column_line_content_width - len(y_max_label_text)) // 2
            y_max_padding = " " * max(0, y_max_padding_count)
            map_grid_lines.append(f"{header_left_padding}{y_max_padding}{y_max_label_text}")

            # --- Assemble the [Full Map] and [Notable Objects] blocks ---
            full_map_text_block = "[Full Map]\n" + "\n".join(map_grid_lines)
            if notable_objects:
                notable_list_str = "\n\n[Notable Objects]"
                sorted_notables_coords = sorted(notable_objects.keys(), key=lambda k: (k[1], k[0])) # Sort by y, then x
                for coord_key in sorted_notables_coords:
                    x_obj, y_obj = coord_key
                    notable_list_str += f"\n({x_obj:2}, {y_obj:2}) {notable_objects[coord_key]}"
                full_map_text_block += notable_list_str
    
    # --- 3. Append the full map text block to the end of processed_state_text ---
    if processed_state_text: # If there's other content before the map
        final_state_text = processed_state_text + "\n\n" + full_map_text_block
    else: # If processed_state_text was empty (e.g., original only had removable sections)
        final_state_text = full_map_text_block
        
    # Final cleanup of multiple newlines (e.g., >2 newlines become 2) and trailing/leading whitespace
    final_state_text = re.sub(r"\n{3,}", "\n\n", final_state_text).strip()
    
    return final_state_text

def replace_filtered_screen_text(state_text: str, dialog_buffer: list[str]) -> str:
    if not dialog_buffer:
        return state_text

    # Generate new section
    new_section = f"[Interacted Dialog Buffer]\n" + "\n".join(dialog_buffer) + "\n\n"

    # Find location of [Filtered Screen Text]
    match = re.search(r"(?=\[Filtered Screen Text\])", state_text)
    if match:
        insert_index = match.start()
        new_state_text = state_text[:insert_index] + new_section + state_text[insert_index:]
        return new_state_text
    else:
        return new_section + "\n" + state_text

