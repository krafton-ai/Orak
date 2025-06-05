# StarCraft II Setup Guide

1. Install [Battle.net](https://download.battle.net/ko-kr?product=bnetdesk) and [StarCraft II]. It requires your own Blizzard account.

2. Save [these SC2Map files](https://github.com/histmeisah/Large-Language-Models-play-StarCraftII/tree/main/Maps) in '''{StarCraft II Install Directory}\Maps''' folder. StarCraft II install directory is usually '''C:\Program Files (x86)\StarCraft II'''

3. Setup the uv or conda env correctly.

4. Run StarCraft II using one of the following commands, depending on the play mode:
- Single-play (Agent vs Bot, using ```play_game.py```)

```
python scripts/play_game.py --config ./src/mcp_agent_client/configs/star_craft/config.yaml
```
- Single-play (Agent vs Bot, using ```mcp_play_game.py```)

```
Work in Progress...
```
- Multi-play (Agent vs Agent, using ```play_game.py```)

```
python scripts/play_game_multi.py --config ./src/mcp_agent_client/configs/star_craft_multi/config.yaml
```
- Multi-play (Agent vs Agent, using ```mcp_play_game.py```)

```
Work in Progress...
```