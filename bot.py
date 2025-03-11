# This example requires the 'message_content' intent.

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

db = {
    'stockpiles': {}
}

@bot.command()
async def CreateStockpile(ctx, hex, town, type, name):
    stock_id = '{}_{}_{}_{}'.format(hex, town, type, name)
    if stock_id in db['stockpiles']:
        await ctx.send('Stockpile already exists')
        return
    db['stockpiles'][stock_id] = {
        'hex': hex,
        'town': town,
        'type': type,
        'name': name
    }
    await ctx.send('New stockpile named '+name+' at the '+type+' in '+town+', '+hex)

@bot.command()
async def DeleteStockpile(ctx, Hex, town, type, name):
    stock_id = '{}_{}_{}_{}'.format(Hex, town, type, name)
    if stock_id not in db['stockpiles']:
        await ctx.send('Stockpile does not exist')
        return
    del db['stockpiles'][stock_id]
    await ctx.send('Deleted stockpile named '+name+' at the '+type+' in '+town+', '+Hex)

@bot.command()
async def UpdateStockpile(ctx, Hex, town, type, name):
    print(ctx.message.content)
    print(ctx.message.attachments[0].content_type)
    await ctx.message.attachments[0].save('{}_{}_{}_{}.png'.format(Hex, town, type, name))
    await ctx.send('Updated stockpile named '+name+' at the '+type+' in '+town+', '+Hex)

bot.run(os.getenv("TOKEN"))

