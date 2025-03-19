import os
import csv

import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

db = {
    int(os.getenv('TESTGUILD_ID')): {
        'stockpiles': {}
    }
}

@bot.event
async def on_ready():
    #guild = discord.Object(id=os.getenv("TESTGUILD_ID"))
    #bot.tree.copy_global_to(guild=guild)
    #await bot.tree.sync(guild=guild)
    print('Tree synced')

@bot.tree.command(name='create', description='Create a new stockpile in the bot')
async def create(inter: discord.Interaction, town: str, type: str, name: str):
    guildid = inter.guild_id
    stock_id = '{}_{}_{}_{}'.format(town, type, name)
    if stock_id in db[guildid]['stockpiles']:
        await inter.response.send_message('Error: Stockpile already exists', ephemeral=True)
        return
    db[guildid]['stockpiles'][stock_id] = {
        'town': town,
        'type': type,
        'name': name,
        'inventory': {'crates': {}, 'items': {}},
        'quotas': {}
    }
    await inter.response.send_message('New stockpile named '+name+' at the '+type+' in '+town)

@bot.tree.command(name='delete', description='Delete a stockpile from the bot')
async def delete(inter: discord.Interaction, town: str, type: str, name: str):
    guildid = inter.guild_id
    stock_id = '{}_{}_{}_{}'.format(town, type, name)
    if stock_id not in db[guildid]['stockpiles']:
        await inter.response.send_message('Error: Stockpile does not exist', ephemeral=True)
        return
    del db[guildid]['stockpiles'][stock_id]
    await inter.response.send_message('Deleted stockpile named '+name+' at the '+type+' in '+town)

@bot.tree.command(name='quota', description='Set quotas for a stockpile')
async def quota(inter: discord.Interaction, town: str, type: str, name: str, quota_list: str):
    guildid = inter.guild_id
    stock_id = '{}_{}_{}_{}'.format(town, type, name)
    if stock_id not in db[guildid]['stockpiles']:
        await inter.response.send_message('Error: Stockpile does not exist', ephemeral=True)
        return
    else:
        stock = db[guildid]['stockpiles'][stock_id]
    for row in quota_list.split(','):
        name, quota = row.split('/')
        if int(quota) < 0:
            del stock['quotas'][name]
        else:
            stock['quotas'][name] = int(quota)
        if len(stock['quotas']) > 0:
            quotas_str = '----------Quotas:----------\n'
            for item, quantity in stock['quotas'].items():
                quotas_str += '{}: {}\n'.format(item, quantity)
    await inter.response.send_message('Updated quotas for stockpile named {} at the {} in {}\n{}'.format(
        name, type, town, quotas_str)
    )

@bot.tree.command(name='requirements', description='Get the requirements from all stockpiles')
async def requirements(inter: discord.Interaction):
    guildid = inter.guild_id
    if len(db[guildid]['stockpiles']) == 0:
        await inter.response.send_message('No stockpiles exist')
        return
    req_dict = {}
    for stock_id, stock in db[guildid]['stockpiles'].items():
        if stock['quotas'] and stock_id not in req_dict:
            req_dict[stock_id] = {}
        for name, quantity in stock['quotas'].items():
            if name in stock['inventory']['crates'] and quantity - stock['inventory']['crates'][name] > 0:
                req_dict[stock_id][name] = quantity - stock['inventory']['crates'][name]
            else:
                req_dict[stock_id][name] = quantity
    if len(req_dict) == 0:
        await inter.response.send_message('No outstanding requirements')
        return
    req_str = '----------Requirements:----------\n'
    for stock_id, reqs in req_dict.items():
        stock = db[guildid]['stockpiles'][stock_id]
        req_str += '{} at the {} in {}\n'.format(
            stock['name'], stock['type'], stock['town']
        )
        for name, quantity in reqs.items():
            req_str += '{}: {}\n'.format(name, quantity)
    await inter.response.send_message(req_str)
        
@bot.tree.command(name='update', description='Update the inventory of a stockpile using a TSV file')
async def update(inter: discord.Interaction, town: str, type: str, name: str):
    guildid = inter.guild_id
    stock_id = '{}_{}_{}_{}'.format(town, type, name)
    if stock_id not in db[guildid]['stockpiles']:
        await inter.response.send_message('Error: Stockpile does not exist', ephemeral=True)
        return
    else:
        stock = db[guildid]['stockpiles'][stock_id]

    await inter.response.send_message("Please reply with your TSV file.")

    def check(msg):
        return msg.author == inter.user and msg.attachments
    
    try:
        msg = await bot.wait_for("message", check=check, timeout=60)  # Wait for 60s
    except asyncio.TimeoutError:
        await inter.followup.send("File upload timed out.", ephemeral=True)
        return

    attachment = msg.attachments[0]
    if 'text/tab-separated-values' not in attachment.content_type:
        await inter.followup.send('Error: File must be a TSV, not {}'.format(attachment.content_type), ephemeral=True)
        return
    
    tsvFile = await attachment.read()
    tsvFile = tsvFile.decode('utf-8').splitlines()
    tsvFile = tsvFile[1:]
    tsvData = csv.reader(tsvFile, delimiter='\t')
    for row in tsvData:
        quantity = int(row[3])
        item_name = row[4]
        crated = True if row[5] == 'true' else False
        if crated:
            stock['inventory']['crates'][item_name] = quantity
        else:
            stock['inventory']['items'][item_name] = quantity
    await inter.followup.send('Updated stockpile named {} at the {} in {}\n'.format(
        name, type, town)
    )

bot.run(os.getenv('TOKEN'))