import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

from data.db_io import DbHandler
import utils.checks as checks
import utils.helpers as helpers

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

bot.db = DbHandler(os.getenv('DB_PATH'))
if len(sys.argv) > 1 and sys.argv[1] == '--sync':
    sync_commands = True
else:
    sync_commands = False


@bot.event
async def on_ready():
    if sync_commands:
        guild = discord.Object(id=os.getenv("TESTGUILD_ID"))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print('Tree synced')


async def setup_hook():
    for file in os.listdir("./commands"):
        #stock.py, preset.py, quota.py, items.py
        if file.endswith(".py"):
            await bot.load_extension(f"commands.{file[:-3]}")


@bot.tree.command(name='register', description='Register this discord server with the bot')
async def register(inter: discord.Interaction):
    bot.db.addGuild(inter.guild_id, inter.guild.name)
    await inter.response.send_message(f"Server {inter.guild.name} is registered")


@bot.tree.command(name='setaccess', description='Set access level of a role on this server (1: User, 2: Admin)')
async def setAccess(inter: discord.Interaction, role: discord.Role, access_level: int):
    try:
        checks.checkRegistration(bot.db, inter.guild_id)
        checks.checkAccessLevel(bot.db, inter, 2)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    bot.db.setAccess(inter.guild_id, role.id, access_level)
    await inter.response.send_message(f"Access level updated for {role.name}")


@bot.tree.command(name='requirements', description='Deprecated. Use "/stock status"')
async def requirements(inter: discord.Interaction, stock_id: int, show_locked: bool=False):
    await inter.response.send_message('Command has been removed. Use "/stock status" instead', ephemeral=True)


bot.setup_hook = setup_hook
bot.run(os.getenv('TOKEN'))