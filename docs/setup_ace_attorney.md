# Ace Attorney Setup Guide

## 1. Prepare the Game
1. Download the official version from Steam: [Phoenix Wright: Ace Attorney Trilogy](https://store.steampowered.com/app/787480/Phoenix_Wright_Ace_Attorney_Trilogy/).
2. Locate the game's installation directory (typically at:  
   `C:\Program Files (x86)\Steam\steamapps\common\Phoenix Wright Ace Attorney Trilogy`):

   ```
   📂 Phoenix Wright Ace Attorney Trilogy\
   ├── PWAAT_Data\
   │   └── Managed\
   │       └── Assembly-CSharp.dll
   ├── PWAAT.exe   (game executable)
   └── UnityPlayer.dll
   ```

## 2. Install BepInEx
1. Download the version corresponding to your operating system from [here](https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.2).  
   *(Tested version in this project: BepInEx_win_x86_5.4.23.2.zip)*
2. Extract the zip file and move all its contents (files and folders) directly into the game's root directory as shown below:

   ```
   📂 Phoenix Wright Ace Attorney Trilogy\
   ├── PWAAT_Data\
   ├── PWAAT.exe   (game executable)
   ├── UnityPlayer.dll
   ├── 📂 BepInEx\
   │   └── core\
   ├── .doorstop_version
   ├── changelog.txt
   ├── doorstop_config.ini
   └── winhttp.dll
   ```

3. Run the game once. A successful launch of BepInEx will result in a directory structure similar to the following:

   ```
   📂 BepInEx\
   ├── cache\
   ├── config\
   ├── core\         (pre-existing files)
   ├── patchers\
   ├── plugins\
   └── LogOutput.log
   ```

4. To enable the console, open `BepInEx/config/BepInEx.cfg`, find the `[Logging.Console]` section, and change the `Enabled` value to `true`: 
   ```ini
   [Logging.Console]

   ## Enables showing a console for log output.
   # Setting type: Boolean
   # Default value: false
   Enabled = true
   ```

## 3. Deployment (Copying to the BepInEx Plugins Folder)
1. Copy `executables\ace_attorney\MyBepInExPlugin.dlll` to the `BepInEx/plugins` folder in your game directory (e.g., `C:\SteamLibrary\steamapps\common\Phoenix Wright Ace Attorney Trilogy\BepInEx\plugins\`).
2. Launch the game:  
   On startup, BepInEx will automatically load the plugin.

## 4. Verification and Debugging
- When the game starts, look for the message `MessageSystemDebugger Loaded` in the console. This confirms that the plugin has been loaded successfully.
- If no log messages appear, verify the following:
  - Confirm that class and method names are correct.
  - Check for any .NET Framework/Standard compatibility issues.
  - Ensure that file paths are correct and free of typos.
  - Validate that the correct version of BepInEx is being used.

# Ace Attorney Evaluation Guide

## 1. (First Run) Create Save Files for Continuing the Game
- Launch the game and create save files by pressing Esc -> Data -> Save when you reach the screens corresponding to the `*_start.png` files located in `C:\Users\keonlee\gamingslm\src\mcp_game_servers\pwaat\game\conversation_log_inputs`.
- At this point, you *must* create exactly 4 save files in the following order. In the **Select a saved data to load.** screen, slots 1 through 4 should contain saves for multiple_choice, cross_examination_1, cross_examination_2, and cross_examination_3 respectively.

## 2. Perform the Specified Number of Trials for Each Task and Calculate Scores
- Verify that `env.auto_savedfile` is set to `True` in `src\mcp_agent_client\configs\pwaat\config.yaml`, then display the **Select a saved data to load.** screen. This is the last step requiring manual game screen manipulation.
- Modify the TaskList, LLMNameList, and AgentTypeList in the `src\mcp_game_servers\pwaat\autorun\autorun_eval.py` file as needed.
- Execute the following command to begin the evaluation. All trials will be performed and evaluated automatically:
  ```bash
  uv run .\src\mcp_game_servers\pwaat\autorun\autorun_eval.py
  ```
- Once all trials are complete, `*_score_card.txt` and `*_score_table.csv` will be generated in the OutputDir.
- (optional) If you want to regenerate `*_score_table.csv` from `*_score_card.txt`, execute the following command:
  ```bash
  uv run src\mcp_game_servers\pwaat\autorun\autorun_convert.py {OutputDir}/*_score_card.txt
  ```
- For the final score, execute the following command. The 'Composite_Grade' column in the generated `{OutputDir}/*_score_grade.csv` represents the final score converted to a 100-point scale:
  ```bash
  uv run src\mcp_game_servers\pwaat\autorun\autorun_grade.py {OutputDir}/*_score_table.csv
  ```
