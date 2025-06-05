
# Street Fighter III Setup Guide

1. Register an account on the [Diambra registration page](https://www.diambra.ai/register)

2. Install [Docker Desktop](https://docs.docker.com/get-started/introduction/get-docker-desktop/) and make sure you have permission to run it.

3. Download the Street Fighter III ROM file (```sfiii3n.zip```) from the internet and place it in the ```executables/streetfighter3/roms``` directory.
- Refer to the [Diambra official installation guide](https://docs.diambra.ai/#installation) for downloading Street Fighter III rom file and checking its validity.

4.  Run Street Fighter III using one of the following commands, depending on the play mode:
- Single-play (Agent vs Bot, using ```play_game.py```)

```
diambra run -r /YOUR/ABSOLUTE/PATH/gamingslm/executables/streetfighter3/roms python scripts/play_game.py --config ./src/mcp_agent_client/configs/street_fighter/config.yaml
```
- Single-play (Agent vs Bot, using ```mcp_play_game.py```)

```
python ./scripts/mcp_play_game.py --config ./src/mcp_agent_client/configs/street_fighter/config.yaml
```

- Multi-play (Agent vs Agent, using ```play_game.py```)
```
diambra run -r /YOUR/ABSOLUTE/PATH/gamingslm/executables/streetfighter3/roms python scripts/play_game_multi.py --config ./src/mcp_agent_client/configs/street_fighter_multi/config.yaml
```
Refer to the [Diambra official installation guide](https://docs.diambra.ai/#installation) for additional setup instructions.
