import os
import csv
import sqlite3

import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from data.db_io import DbHandler

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

db = DbHandler(os.getenv('DB_PATH'))

@bot.event
async def on_ready():
    #guild = discord.Object(id=os.getenv("TESTGUILD_ID"))
    #bot.tree.copy_global_to(guild=guild)
    #await bot.tree.sync(guild=guild)
    print('Tree synced')


@bot.tree.command(name='register', description='Register this discord server with the bot')
async def register(inter: discord.Interaction):
    try:
        db.addGuild(inter.guild_id, inter.guild.name)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message('Registered server {}'.format(inter.guild.name))


@bot.tree.command(name='list', description='List all stockpiles registered on the discord server')
async def list(inter: discord.Interaction):
    stockpiles = db.fetchStockpiles(inter.guild_id)
    if stockpiles == []:
        await inter.response.send_message('No stockpiles registered for this server', ephemeral=True)
        return
    stock_list = ['Stock ID   |   Name   |   Town   |   Type']
    for stock in stockpiles:
        stock_list.append(f"{stock['id']}   |   {stock['name']}   |   {stock['town']}   |   {stock['type']}")
    stock_str = '\n'.join(stock_list)
    await inter.response.send_message(stock_str)


@bot.tree.command(name='create', description='Create a new stockpile in the bot')
async def create(inter: discord.Interaction, town: str, type: str, name: str):
    try:
        db.create(inter.guild_id, town, type, name)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message(f"Created stockpile named {name} at the {type} in {town}")


@bot.tree.command(name='delete', description='Delete a stockpile from the bot')
async def delete(inter: discord.Interaction, stock_id: int):
    try:
        db.delete(inter.guild_id, stock_id)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message(f"Deleted stockpile with ID {stock_id}")


@bot.tree.command(name='addquotas', description="""Set quotas for a stockpile. 
quota_list in the form \"display_name:quantity, display_name:quantity\"""")
async def addQuotas(inter: discord.Interaction, stock_id: int, quota_list: str):
    try:
        db.addQuotas(inter.guild_id, stock_id, quota_list)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message(f"Added quotas to stockpile with ID {stock_id}")


@bot.tree.command(name='requirements', description='Get the requirements from all stockpiles')
async def requirements(inter: discord.Interaction):
    try:
        req_dict = db.getRequirements(inter.guild_id)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    if not req_dict:
        await inter.response.send_message('No requirements found', ephemeral=True)
        return
    req_list = ['```Stock ID | Quantity |  Crates Needed \n----------------------------------------------']
    for stock_id, reqs in req_dict.items():
        for item, quantity in reqs['requirements'].items():
            req_list.append(f"{stock_id: <8} | {quantity: <8} | {item} ")
    req_str = '\n'.join(req_list)+'```'
    await inter.response.send_message(req_str)

  
@bot.tree.command(name='update', description='Update the inventory of a stockpile using a TSV file')
async def update(inter: discord.Interaction, stock_id: int):
    # Prompt user for TSV file
    await inter.response.send_message("Please reply with your TSV file.")
    def check(msg):
        return msg.author == inter.user and msg.attachments
    try:
        msg = await bot.wait_for("message", check=check, timeout=60)  # Wait for 60s
    except asyncio.TimeoutError:
        await inter.followup.send("File upload timed out.", ephemeral=True)
        return

    # Ingest TSV file
    attachment = msg.attachments[0]
    if 'text/tab-separated-values' not in attachment.content_type:
        await inter.followup.send('Error: File must be a TSV, not {}'.format(attachment.content_type), ephemeral=True)
        return
    tsvFile = await attachment.read()
    tsvFile = tsvFile.decode('utf-8').splitlines()
    try:
        db.updateInventory(inter.guild_id, stock_id, tsvFile)
    except ValueError as e:
        await inter.followup.send(str(e), ephemeral=True)
        return
    await inter.followup.send('Updated stockpile with ID {}'.format(stock_id))

bot.run(os.getenv('TOKEN'))