# Her Story Setup Guide

## 1. Install the Game

- Purchase and install **[Her Story](https://store.steampowered.com/app/368370/Her_Story/)** from Steam.

## 2. Install the Plugin

### 2.1. Install Unity Doorstop

Download [Unity Doorstop v4.4.0](https://github.com/NeighTools/UnityDoorstop/releases/tag/v4.4.0) and copy the required files:

- **Windows**:
  - Download `doorstop_win_release_4.4.0.zip` → `x86` folder
  - Copy `winhttp.dll` and `doorstop_config.ini` to the game's root folder: `C:\Program Files (x86)\Steam\steamapps\common\HER STORY`
  - Open `doorstop_config.ini` and set:

    ```ini
    target_assembly=HerStoryPlugin.dll
    ```

- **macOS**:
  - Download `doorstop_macos_release_4.4.0.zip` → `x64` folder
  - Locate `libdoorstop.dylib` and `run.sh` in the same directory. You can place these files in any directory.
  - Open `run.sh` and set:

    ```bash
    executable_name="$HOME/Library/Application Support/Steam/steamapps/common/HER STORY/Her Story.app"
    target_assembly="HerStoryPlugin.dll"
    ```

### 2.2. Install Harmony

Download [Harmony v2.3.6](https://github.com/pardeike/Harmony/releases/tag/v2.3.6.0):

- Download `Harmony-Fat.2.3.6.0.zip` → `net35` folder
- Copy `0Harmony.dll` into the same directory as Unity Doorstop.

### 2.3. Add the Plugin DLL

Copy `executables/her_story/HerStoryPlugin.dll` into the same directory as Unity Doorstop.

## 3. Run the Game

- **Windows**:
  1. Launch the game by executing `C:\Program Files (x86)\Steam\steamapps\common\HER STORY\HerStory.exe`
  2. You can find game logs in `C:\Program Files (x86)\Steam\steamapps\common\HER STORY\game_log.txt`
- **macOS**:
  1. Run the game by executing `run.sh`
  2. You can find game logs in `~/Library/Application Support/Steam/steamapps/common/HER STORY/game_log.txt`

## 4. Configure the LLM Evaluation

### 4.1. Configure Environment

Open `src/mcp_agent_client/configs/her_story/config.yaml` and `src/mcp_game_servers/her_story/config.yaml` and modify:

```yaml
env:
  state_path: "PATH/OF/THE/GAME/LOG/FILE"
  speedrun: true  # set "false" if you don't want to skip videos
  max_steps: 400  # it should be equivalent to the runner.max_steps
  reset_after_stop: false  # set "true" if you want to automatically reset the game after the evaluation
  input_modality: "text"  # "text", "text_image"
  censor_contents: false  # gemini: "true"
  io_env:
    win_name_pattern: "^HerStory$"  # Windows: "^HerStory$", macOS: "^Her Story$"
```

### 4.2. Configure Agent

Open `src/mcp_agent_client/configs/her_story/config.yaml` and `src/mcp_agent_servers/her_story/config.yaml` and modify:

```yaml
agent:
  llm_name: gpt-4o  # "gpt-4o-mini", "gpt-4o", "o3-mini", "claude-3-7-sonnet-20250219", "deepseek-reasoner"
  api_key: "token-abc123"  # only for local model
  api_base_url: "http://localhost:8000/v1"  # only for local model
  temperature: 0.3
  repetition_penalty: 1.0
  agent_type: zeroshot_agent  # zeroshot_agent, reflection_agent, planning_agent, reflection_planning_agent
  prompt_path: mcp_agent_servers.her_story.prompts.text.zeroshot_agent  # it should be equivalent to {{env.input_modality}}.{{agent.agent_type}}
```

## 5. Run the LLM Evaluation

1. Start the game manually.

    - Ensure the game is running in windowed mode.
    - If you are using multiple monitors, place the game window on the main display.

2. If you have already played the game before, delete session data from the settings panel
3. Make sure the game is at the main title screen showing the Start button
4. In your terminal, run the evaluation:

    ```bash
    uv run ./scripts/mcp_play_game.py --config ./src/mcp_agent_client/configs/her_story/config.yaml
    ```

## Note

### Details about Her Story Mod

It is designed to log game state data in real-time.

#### Logging Behavior

1. Loading main title screen

    - Status: title
    - Log:
      - Screen resolution

2. Game start

    - Status: start_game
    - Log:
      - Screen resolution
      - Position of text input field
      - Initial keyword written in text input field
      - Position of settings button

3. Execute query

    - Status: query
    - Log:
      - Keyword

4. Get keyword result

    - Status: query_result
    - Log:
      - Keyword
      - Summary text
      - Total and visible result count
      - Each video's ID, in-game ID, session date, outfit description, position of thumbnail, "new" status
      - Screen resolution
      - Position of text field
      - Position of settings button
      - Chat unlock state
      - Read count and flag count

5. Open video panel
    - Status: open_detail
    - Log:
      - Video ID, in-game ID, session date, outfit description
      - Position of thumbnail
      - Position of close button
      - Screen resolution

6. Close video panel
    - Status: close_detail

7. Play video
    - Status: play_video
    - Log:
      - Video ID, in-game ID, session date, outfit
      - Transcript
      - Number of reads and flags

8. Close video
    - Status: close_video

9. Open settings menu
    - Status: open_setting
    - Log:
      - Position of "Delete Game" button
      - Position of "QUIT" button, which is visible after clicking "Delete Game" button

10. Reset game
    - Status: reset_game
