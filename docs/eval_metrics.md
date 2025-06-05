# 📊 Evaluation Metrics

Here, we summarize all the evaluation metrics used for each game in Orak. The code for evaluation criterion can be find in `def evaluate(self, obs)` function on `./src/mcp_game_servers/{game}/game/{game}_env.py`. For examples, see the [evaluation function](../src/mcp_game_servers/twenty_fourty_eight/game/twenty_fourty_eight_env.py) for 2048.


## Street Fighter III.

> $Score = \text{\{ Number of stages cleared by the agent\} }/ \{ \text{Total Number of stages}\} \times 100$,

where 'Total Number of stages' is 10.


## Super Mario.

> $Score = \text{\{ Distance that Mario traversed\} } /\text{\{ Distance to Flag from the starting point\} } \times 100$.

## Ace Attorney.



## Her Story.

> $Score = \text{\{ Number of distinct video clips viewed\} } /\text{\{ Total Number of video clips \} } \times 100$,

where 'Total Number of stages' is 272.


## Pokémon Red.

> $Score = \text{\{ Number of flas achieved\} } /\text{\{ Total Number of flags\} } \times 100$,

where 'Total Number of flags' is 12 with a flag set of `Exit Red's House`, `Encounter Professor Oak`, `Choose a starter Pokémon`, `Finish the first battle with the Rival`, `Arrive in Viridian City`, `Receive Oak's parcel`, `Deliver Oak's parcel to Professor Oak`, `Obtain the Town Map`, `Purchase a Poké Ball`, `Catch a new Pokémon`, `Arrive in Pewter City`, and `Defeat Pewter Gym Leader Brock`.

## Darkest Dungeon.



## Minecraft.

> $Score = \text{\{ Number of items crafted\} } /\text{\{ Total Number of items\} } \times 100$,

where 'Total Number of items' is 8 with an item set of `crafting table`, `stone pickaxe`, `furnace`, `bucket`, `golden sword`, `diamond pickaxe`, `enchanting table`, and `nether portal`.


## Stardew Valley.

> $Score = \text{\{ Amount of gold earned \} } /\text{\{ Maximum amount of gold earned by an oracle\} } \times 100$,

where 'Maximum amount of gold earned by an oracle' is 1013.


## StarCraft II.

> $Score = \text{\{ Number of wins against AI bot \} } /\text{\{ Total matches played\} } \times 100$.


## Slay the Spire.

> $Score = 0.5 \times \text{\{ Number of cleared floors \} } /\text{\{ Total number of floors\} } + 0.5  \times \text{\{ Number of bosses defeated \} } /\text{\{ Total number of bosses\} }  \times 100$,

where `Total number of floors` is 50 and `Total number of bosses` is 3.

## Baba Is You.

> $Score =~~~100~~~\text{if level is cleared},~~~40~~~\text{if `Wall Is Stop` is broken and `Win` rule is created},~~~20~~~\text{if level is cleared}$,

where `Total number of floors` is 50 and `Total number of bosses` is 3.

## 2048.

> $Score =min(\text{Final Game Score/20000, 1})*100$,

where `Final Game Score` is the original game score of 2048, and `20,000` is the game score generally achieved by the human expert. 
