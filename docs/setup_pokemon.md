## Setup Instructions

1. **Install PyBoy**

   ```bash
   pip install pyboy==2.5.2
   ```

2. **Add the ROM File**
   Place a legally obtained, license-compliant Pokémon Red ROM file in the following location:
   ```bash
   ./executables/pokemon_red/pyboy/pokered.gbc
   ```
   **Recommended**:
      Before running the full automation, launch the game once and create a save file with your desired player and rival names.
      This helps avoid early-game menu handling issues.
      You can run the game by
      ```bash
      python -m pyboy ./executables/pokemon_red/pyboy/pokered.gbc
      ```

3. **Download Map Object Data**

   Download the [pokered GitHub repository](https://github.com/pret/pokered), and place it into your project directory at:

   ```
   "./src/mcp_game_servers/pokemon_red/game/pokered"
   ```

   Then, run the following command to make map files.
   
   ```bash
   python ./src/mcp_game_servers/pokemon_red/game/utils/map_preprocess.py
   ```

4. **Run the Script**

   ```bash
   bash ./scripts/leaderboard/python/pokemon_red.sh
   ```

Reference
- https://github.com/pret/pokered
- https://datacrystal.tcrf.net/wiki/Pok%C3%A9mon_Red_and_Blue
