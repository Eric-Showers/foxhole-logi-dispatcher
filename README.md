# Foxhole Logi Dispatcher
Discord bot for use with the game Foxhole which creates logistics tasks based on set requirements and current inventories.

## Acknowledgements
Thanks to [FIR](https://github.com/GICodeWarrior/fir) for their excelent stockpile scanner which this bot cannot live without. Thanks to [FoxAPI](https://github.com/ThePhoenix78/FoxAPI) for the war API wrapper which helps pull data on the world state.

## Commands

### /register
Registers the discord server with the database. This is required before all other commands.

### /list
Lists all the current stockpiles in the database for this discord server.

### /create
Adds a new stockpile to the database.

### /delete
Deletes a stockpile from the database.

### /update
Updates a stockpile's inventory using a TSV file from [FIR](https://github.com/GICodeWarrior/fir).

### /addquotas
Adds minimum crate requirements to a stockpile.

### /requirements
Lists the current requirements for all stockpiles based on their quotas.
