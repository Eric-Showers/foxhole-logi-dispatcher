# This example requires the 'message_content' intent.

import os
import csv

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

db = {
    'testguild': {
        'stockpiles': {}
    }
}

@bot.command()
async def CreateStockpile(ctx, hex, town, type, name):
    guildid = 'testguild'
    stock_id = '{}_{}_{}_{}'.format(hex, town, type, name)
    if stock_id in db[guildid]['stockpiles']:
        await ctx.send('Stockpile already exists')
        return
    db[guildid]['stockpiles'][stock_id] = {
        'hex': hex,
        'town': town,
        'type': type,
        'name': name,
        'inventory': {
            'crates': {},
            'items': {}
        },
        'quotas': {}
    }
    await ctx.send('New stockpile named '+name+' at the '+type+' in '+town+', '+hex)

@bot.command()
async def DeleteStockpile(ctx, Hex, town, type, name):
    guildid = 'testguild'
    stock_id = '{}_{}_{}_{}'.format(Hex, town, type, name)
    if stock_id not in db[guildid]['stockpiles']:
        await ctx.send('Error: Stockpile does not exist')
        return
    del db[guildid]['stockpiles'][stock_id]
    await ctx.send('Deleted stockpile named '+name+' at the '+type+' in '+town+', '+Hex)

@bot.command()
async def SetQuota(ctx, Hex, town, type, name, quota_list):
    guildid = 'testguild'
    stock_id = '{}_{}_{}_{}'.format(Hex, town, type, name)
    if stock_id not in db[guildid]['stockpiles']:
        await ctx.send('Error: Stockpile does not exist')
        return
    else:
        stock = db[guildid]['stockpiles'][stock_id]
    for row in quota_list.splitlines():
        name, quota = row.split(',')
        if int(quota) < 0:
            del stock['quotas'][name]
        else:
            stock['quotas'][name] = int(quota)
        if len(stock['quotas']) > 0:
            quotas_str = '----------Quotas:----------\n'
            for item, quantity in stock['quotas'].items():
                quotas_str += '{}: {}\n'.format(item, quantity)
    await ctx.send('Updated quotas for stockpile named {} at the {} in {}, {}\n{}'.format(
        name, type, town, Hex, quotas_str)
    )

@bot.command()
async def GetRequirements(ctx):
    guildid = 'testguild'
    if len(db[guildid]['stockpiles']) == 0:
        await ctx.send('No stockpiles exist')
        return
    req_dict = {}
    for stock_id, stock in db[guildid]['stockpiles'].items():
        for name, quantity in stock['quotas'].items():
            if name in stock['inventory']['crates'] and stock['inventory']['crates'][name] <= quantity:
                if stock_id not in req_dict:
                    req_dict[stock_id] = {}
                req_dict[stock_id][name] = quantity - stock['inventory']['crates'][name]
    if len(req_dict) == 0:
        await ctx.send('No outstanding requirements')
        return
    req_str = '----------Requirements:----------\n'
    for stock_id, reqs in req_dict.items():
        stock = db[guildid]['stockpiles'][stock_id]
        req_str += '{} at the {} in {}, {}\n'.format(
            stock['name'], stock['type'], stock['town'], stock['hex']
        )
        for name, quantity in reqs.items():
            req_str += '{}: {}\n'.format(name, quantity)
    await ctx.send(req_str)
        
@bot.command()
async def UpdateStockpile(ctx, Hex, town, type, name):
    guildid = 'testguild'
    stock_id = '{}_{}_{}_{}'.format(Hex, town, type, name)
    if stock_id not in db[guildid]['stockpiles']:
        await ctx.send('Error: Stockpile does not exist')
        return
    else:
        stock = db[guildid]['stockpiles'][stock_id]
    if len(ctx.message.attachments) == 0:
        await ctx.send('Error: No file attached')
        return
    if 'text/tab-separated-values' not in ctx.message.attachments[0].content_type:
        await ctx.send('Error: File must be a TSV, not {}'.format(ctx.message.attachments[0].content_type))
        return
    print(ctx.message.attachments[0].content_type)
    tsvFile = await ctx.message.attachments[0].read()
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
    if len(stock['inventory']['crates']) > 0:
        inventory_str = '----------Crates:----------\n'
        for item, quantity in stock['inventory']['crates'].items():
            inventory_str += '{}: {}\n'.format(item, quantity)
    if len(stock['inventory']['items']) > 0:
        inventory_str += '----------Items:----------\n'
        for item, quantity in stock['inventory']['items'].items():
            inventory_str += '{}: {}\n'.format(item, quantity)
    await ctx.send('Updated stockpile named {} at the {} in {}, {}\nNew Inventory:\n{}'.format(
        name, type, town, Hex, inventory_str)
    )
    


bot.run(os.getenv("TOKEN"))