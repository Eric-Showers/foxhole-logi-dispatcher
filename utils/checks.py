import discord

from data.db_io import DbHandler


def checkRegistration(db: DbHandler, guild_id):
    if not db.checkRegistration(guild_id):
        raise discord.app_commands.CheckFailure('Discord server not registered. Use `/register`')


def checkAccessLevel(db: DbHandler, inter: discord.Interaction, required_level):
    if inter.user.id == inter.guild.owner_id:
        return
    elif inter.user.guild_permissions.manage_guild:
        return
    access_level = db.getAccessLevel(inter.guild_id, [r.id for r in inter.user.roles])
    if access_level < required_level:
        raise discord.app_commands.CheckFailure('You do not have the necessary roles to use this command')


def checkStockId(db: DbHandler, inter: discord.Interaction, stock_id):
    if not db.checkStockIdAccess(inter.guild_id, stock_id):
        raise discord.app_commands.CheckFailure(f"No stock with ID {stock_id} exists for this server")
    

def checkPreset(db: DbHandler, inter: discord.Interaction, preset_name):
    if not db.checkPresetAccess(inter.guild_id, preset_name):
        raise discord.app_commands.CheckFailure(f"No preset with name {preset_name} exists for this server")
