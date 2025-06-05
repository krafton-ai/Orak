# Stardew Valley Setup Guide

*(Only Windows is supported currently.)*

---

## 1. Install the Game
- Download and install [Stardew Valley](https://store.steampowered.com/app/413150/Stardew_Valley/) from Steam.

## 2. Install StateExtractor Mod

### Step 1: Install SMAPI

Follow the instruction in [Stardew Valley Wiki](https://stardewvalleywiki.com/Modding:Player_Guide/Getting_Started) to install SMAPI.

### Step 2: Install StateExtractor

- Copy [mod zip file](../executables/stardew_valley/StateExtractor.zip) to Stardew Valley game folder and unzip.
    - Game folder is typically located as follows:
        - Windows: `C:\Program Files (x86)\Steam\steamapps\common\Stardew Valley`
    - Unzipped folder structure should be `./Mods/StateExtractor/{config.json, maifest.json, StateExtractor.dll}`.

- Setup configuration (`StateExtractor/config.json`).
    - `StateSavePath` and `ActionSavePath` should be modified correspond to your project path.

### Step 3: Setup Save File
- Copy [save file](../executables/stardew_valley/save.zip) to Stardew Valley Save folder and unzip.
    - Save folder is typically located at:
        - Windows: `%APPDATA%\StardewValley\Saves`

## 3. To-do Before Each Evaluation Run

- Load save file.
- Set max energy to 50 by toggle energy button `F5`.
- Set focus on Stardew Valley Game after run script. 

## Note

### Details about StateExtractor Mod

StateExtractor is a Stardew Valley mod designed to extract and log structured game state data in real-time. It captures detailed snapshots of the current game environment, player information, and farm status, storing them in JSON format for later analysis or integration with external tools.

#### Features

- **Player Tracking**
  - Logs player position, direction, location, money, and stamina.
  
- **World State**
  - Records current day, season, weather, and number of tilled but unplanted tiles.

- **Obstacle Detection**
  - Identifies and records various obstacles (stone, weed, twig, tree, grass) on the farm.
  - Includes tilled soil and crop tile data.

- **Toolbar Inventory**
  - Captures complete toolbar inventory, including selected item metadata.

- **Crop Logging**
  - Logs planted crop type, position, days remaining to harvest, and watered status.

- **Shop Interaction**
  - Captures shop inventories when a shop menu is opened.

- **Hotkey Automations**
  - `P`, `G`, `H`: Warp to key locations (Farm, Seed Shop, Farmhouse).
  - `L`, `Right-click` in Pierre’s shop: Open Seed Shop menu.
  - `O`: Plant seeds on already tilled soil.
  - `I`: Water all planted crops.
  - `U`: Harvest all ready crops.
  - `K`: Sell specific crops from inventory (e.g., Parsnip, Potato).
  - `J`: Till soil based on parameters in an external JSON file.
  - `F5`: Toggle max energy between 50 and 270.
  - `R`: Close any open menu.

#### Logging Behavior

- Game state is logged on:
  - Player warp
  - Menu open (Shop)
  - New day start
  - Input button release

- Logs are skipped if no change is detected since the last log to avoid redundancy.

#### Configuration

- The mod reads from `config.json` for:
  - Save paths for state and action logs.
  - Bounds for soil tilling and obstacle tracking.

- JSON logs are saved with timestamped filenames.
