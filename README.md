# Foxhole Logi Dispatcher
Discord bot for use with the game Foxhole which creates logistics tasks based on set requirements and current inventories.

## Acknowledgements
Thanks to [FIR](https://github.com/GICodeWarrior/fir) for their excelent stockpile scanner which this bot cannot live without. Thanks to [FoxAPI](https://github.com/ThePhoenix78/FoxAPI) for the war API wrapper which helps pull data on the world state.

## Directory Structure
```
.
├── commands                # Discord command groups
├── data                    # Database interface and init script
├── utils                   # Checks and helper functions
├── bot.py                  # Top-level discord logic
└── requirements.txt        # Python dependencies
```

## Planned Updates

i) Create automated interface with FIR to enable the bot to process screenshots by itself

ii) When checking the status of a stockpile with `/requirements`, the bot could search for the required items in other stockpiles and indicate items which can be delivered from another stockpile vs. items which need to be produced.

iii) Add a /tasks command which returns individual in-game tasks that can be done, like "Fill a container with X bmats, Y shirts, ... at Jade Cove and drive it to Longstone"

iv) Use discord app views to create custom displays. Add buttons for related commands.