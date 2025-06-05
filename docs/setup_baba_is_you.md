# Baba Is You Setup Guide

This guide explains how to install and set up mod scripts for **Baba Is You** on **Windows** and **macOS**.

---

## 1. Install the Game

- Purchase and install **[Baba Is You](https://store.steampowered.com/app/736260/Baba_Is_You/)** from Steam.

---

## 2. Add Mod Scripts

To enable interaction with the game, you need to add custom Lua scripts to the game’s data directory.

### Locate the `Lua` Folder:

- **Windows:**
  ```bash
  C:\Program Files (x86)\Steam\steamapps\common\Baba Is You\Data\Lua
  ```

- **macOS:**
  ```bash
  ~/Library/Application Support/Steam/steamapps/common/Baba Is You/Contents/Resources/Data/Lua
  ```

### Copy the Mod Scripts:

From your repository, copy the following Lua files:

```bash
src/mcp_game_servers/baba_is_you/game/mod_scripts/dkjson.lua
src/mcp_game_servers/baba_is_you/game/mod_scripts/game_state.lua
```

Paste them into the `Lua` folder you located above.

---

## 3. Configuration Setup

Ensure your environment is properly configured:

- **state_json_path**:
  - **Windows:**
    ```bash
    %APPDATA%/Baba_Is_You/state.ba
    ```
  - **macOS:**
    ```bash
    ~/Library/Application Support/Baba_Is_You/state.ba
    ```

- **level_name**: The default evaluation level is:
  ```
  "where do i go?"
  ```

 ---

# Baba Is You Evaluation Guide

Before running the `mcp_play_game.py` script:

1. **Start the game manually.**
2. **Complete the tutorial level** ("Level 0") so that Level 1 becomes accessible.
3. **Navigate to Level 1**: `"where do i go?"`
4. **Move Baba at least once** (e.g., up and down) to trigger a game state update.  
   > This ensures that the mod script saves the initial state correctly.
5. Now you can run:
   ```bash
   uv run ./scripts/mcp_play_game.py --config ./src/mcp_agent_client/configs/baba_is_you/config.yaml
   ```