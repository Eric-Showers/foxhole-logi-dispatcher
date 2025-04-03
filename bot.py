import os
import time

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
sync_commands = False


@bot.event
async def on_ready():
    if sync_commands:
        guild = discord.Object(id=os.getenv("TESTGUILD_ID"))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print('Tree synced')


def checkRegistration(guild_id):
    if not db.checkRegistration(guild_id):
        raise discord.app_commands.CheckFailure('Discord server not registered. Use `/register`')


def checkAccessLevel(inter: discord.Interaction, required_level):
    if inter.user.id == inter.guild.owner_id:
        return
    elif inter.user.guild_permissions.manage_guild:
        return
    access_level = db.getAccessLevel(inter.guild_id, [r.id for r in inter.user.roles])
    if access_level < required_level:
        raise discord.app_commands.CheckFailure('You do not have the necessary roles to use this command')


def checkStockId(inter: discord.Interaction, stock_id):
    if not db.checkStockIdAccess(inter.guild_id, stock_id):
        raise discord.app_commands.CheckFailure(f"No stock with ID {stock_id} exists for this server")
    

def checkPreset(inter: discord.Interaction, preset_name):
    if not db.checkPresetAccess(inter.guild_id, preset_name):
        raise discord.app_commands.CheckFailure(f"No preset with name {preset_name} exists for this server")


@bot.tree.command(name='register', description='Register this discord server with the bot')
async def register(inter: discord.Interaction):
    db.addGuild(inter.guild_id, inter.guild.name)
    await inter.response.send_message(f"Server {inter.guild.name} is registered")


@bot.tree.command(name='setaccess', description='Set access level of a role on this server (1: User, 2: Admin)')
async def setAccess(inter: discord.Interaction, role: discord.Role, access_level: int):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    db.setAccess(inter.guild_id, role.id, access_level)
    await inter.response.send_message(f"Access level updated for {role.name}")


@bot.tree.command(name='list', description='List all stockpiles registered on the discord server')
async def list(inter: discord.Interaction):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 1)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    
    stockpiles = db.fetchStockpiles(inter.guild_id)
    if not stockpiles:
        await inter.response.send_message('No stockpiles found', ephemeral=True)
        return
    stock_str = '```Stock ID |     Name     |        Town        |     Type     |   Last Updated\n--------------------------------------------------'
    for stock in stockpiles:
        stock_str += "\n{: <8} | {: <12} | {: <18} | {: <12} | {}".format(
            stock['id'],
            stock['name'],
            stock['town'],
            stock['type'],
            get_relative_time_str(stock['last_update'])
        )
    stock_str += '```'
    await inter.response.send_message(stock_str)


@bot.tree.command(name='create', description='Add a new stockpile in the bot')
async def create(inter: discord.Interaction, town: str, type: str, name: str):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    try:
        db.create(inter.guild_id, town, type, name)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message(f"Created stockpile named {name} at the {type} in {town}")


@bot.tree.command(name='delete', description='Delete a stockpile from the bot')
async def delete(inter: discord.Interaction, stock_id: int):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
        checkStockId(inter, stock_id)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    db.delete(stock_id)
    await inter.response.send_message(f"Deleted stockpile with ID {stock_id}")


@bot.tree.command(name='update', description='Update the inventory of a stockpile using a TSV file')
async def update(inter: discord.Interaction, stock_id: int):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
        checkStockId(inter, stock_id)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    # Prompt user for TSV file
    await inter.response.send_message("Please reply with your TSV file.")
    def check(msg):
        return (
            msg.author == inter.user 
            and msg.channel == inter.channel
            and msg.attachments
        )
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
        db.updateInventory(stock_id, tsvFile)
    except ValueError as e:
        await inter.followup.send(str(e), ephemeral=True)
        return
    await inter.followup.send('Updated stockpile with ID {}'.format(stock_id))


@bot.tree.command(name='updatemulti', description='Update the inventory of multiple stockpiles using a TSV file. (stock_ids: 1, 3, 4, ...)')
async def updateMulti(inter: discord.Interaction, stock_ids: str):
    stock_ids = [int(id.strip()) for id in stock_ids.split(',')]
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
        for id in stock_ids:
            checkStockId(inter, id)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    # Prompt user for TSV file
    await inter.response.send_message("Please reply with your TSV file.")
    def check(msg):
        return (
            msg.author == inter.user 
            and msg.channel == inter.channel
            and msg.attachments
        )
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
        stock_ids = db.updateMulti(stock_ids, tsvFile)
    except ValueError as e:
        await inter.followup.send(str(e), ephemeral=True)
        return
    await inter.followup.send(f"Updated stockpiles with IDs {stock_ids}")


@bot.tree.command(name='addquotas', description="""Adds quotas to a stockpile. 
Vehicle amounts uncrated. quota_list in the form name:amount, name:...""")
async def addQuotas(inter: discord.Interaction, stock_id: int, quota_list: str):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
        checkStockId(inter, stock_id)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    try:
        db.addQuotas(stock_id, quota_list)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message(f"Added quotas to stockpile with ID {stock_id}")


@bot.tree.command(name='deletequotas', description="Removes all quotas for a stockpile.")
async def deleteQuotas(inter: discord.Interaction, stock_id: int):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
        checkStockId(inter, stock_id)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    db.deleteQuotas(stock_id)
    await inter.response.send_message(f"Deleted quotas for stockpile with ID {stock_id}")


@bot.tree.command(name='listquotas', description='List the quotas that are set on a stockpile')
async def listQuotas(inter: discord.Interaction, stock_id: int):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 1)
        checkStockId(inter, stock_id)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    quota_list = db.fetchQuotas(stock_id)
    if quota_list == []:
        await inter.response.send_message(f"No quotas found on stock ID {stock_id}", ephemeral=True)
        return
    
    # Build table
    categorized = organizeItemList(quota_list)
    quota_table = ['Category   |  Quantity  | Item Name\n-----------------------------------']
    for cat, quotas in categorized.items():
        quota_table.append(f"{cat: <10} | {quotas[0]['quantity']: <10} | {quotas[0]['display_name']}")
        for q in quotas[1:]:
            quota_table.append(f"{'': <10} | {q['quantity']: <10} | {q['display_name']}")
    resp_str = '\n'.join(quota_table)
    resp_str += '\n\nQuota set string:\n'+', '.join([f"{q['info']['display_name']}:{q['quantity']}" for q in quota_list])
    
    # Handle overflow
    chunks = chunk_response(resp_str)
    await inter.response.send_message(f"```{chunks[0]}```")
    for chunk in chunks[1:]:
        await inter.followup.send(f"```{chunk}```")


@bot.tree.command(name='createpreset', description='Create a quota preset. quota_list must be same format as for /addquotas')
async def createPreset(inter: discord.Interaction, preset_name: str, quota_list:str):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    if quota_list == '':
        await inter.response.send_message('Quota list is empty', ephemeral=True)
        return
    try:
        db.createPreset(inter.guild_id, preset_name, quota_list)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message(f"Preset {preset_name} created succesfully")


@bot.tree.command(name='deletepreset', description='Deletes a named preset (does not remove from active quotas)')
async def deletePreset(inter: discord.Interaction, preset_name: str):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
        checkPreset(inter, preset_name)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    try:
        db.deletePreset(inter.guild_id, preset_name)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message(f"Preset {preset_name} deleted successfully")


@bot.tree.command(name='applypreset', description='Adds a preset quota to a stockpile (does not overwrite existing quotas)')
async def applyPreset(inter: discord.Interaction, stock_id: str, preset_name: str):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 2)
        checkStockId(inter, stock_id)
        checkPreset(inter, preset_name)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    try:
        db.applyPreset(inter.guild_id, stock_id, preset_name)
    except ValueError as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    await inter.response.send_message(f"Preset {preset_name} added to stockpile with id {stock_id}")


@bot.tree.command(name='listpresets', description='List all preset names')
async def listPresets(inter: discord.Interaction):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 1)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    preset_list = db.fetchPresets(inter.guild_id)
    if preset_list == []:
        await inter.response.send_message('No presets found for this server', ephemeral=True)
        return
    preset_str = '```Preset Names\n-------------\n{}```'.format('\n'.join(preset_list))
    await inter.response.send_message(preset_str)


@bot.tree.command(name='showpreset', description='Show the contents of a preset')
async def showPreset(inter: discord.Interaction, preset_name: str):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 1)
        checkPreset(inter, preset_name)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    quota_list = db.fetchPresetList(inter.guild_id, preset_name)
    categorized = organizeItemList(quota_list)

    # Build table
    quota_table = ['Category   |  Quantity  | Item Name\n-----------------------------------']
    for cat, quotas in categorized.items():
        quota_table.append(f"{cat: <10} | {quotas[0]['quantity']: <10} | {quotas[0]['display_name']}")
        for q in quotas[1:]:
            quota_table.append(f"{'': <10} | {q['quantity']: <10} | {q['display_name']}")
    quota_string = '\n'.join(quota_table)

    # Handle overflow
    chunks = chunk_response(quota_string)
    await inter.response.send_message(f"```{chunks[0]}```")
    for chunk in chunks[1:]:
        await inter.followup.send(f"```{chunk}```")


@bot.tree.command(name='requirements', description='Get the required crates to meet quotas on a stockpile')
async def requirements(inter: discord.Interaction, stock_id: int):
    try:
        checkRegistration(inter.guild_id)
        checkAccessLevel(inter, 1)
        checkStockId(inter, stock_id)
    except discord.app_commands.CheckFailure as e:
        await inter.response.send_message(str(e), ephemeral=True)
        return
    req_dict = db.getRequirements(stock_id)
    if req_dict == {}:
        await inter.response.send_message(f"No outstanding requirements found for stock ID {stock_id}", ephemeral=True)
        return
    categorized = organizeItemList(req_dict['requirements'])

    # Build response table
    reqs_table = ["({}, {} {}, ID: {}, last updated: {})\n".format(
        req_dict['name'],
        req_dict['town'],
        req_dict['type'],
        stock_id,
        get_relative_time_str(req_dict['last_update'])
    )]
    reqs_table.append('Category   | Quantity | Item Name\n-----------------------------------')
    for cat, cat_items in categorized.items():
        reqs_table.append(f"{cat: <10} | {cat_items[0]['quantity']: <8} | {cat_items[0]['display_name']}")
        for item in cat_items[1:]:
            reqs_table.append(f"{'': <10} | {item['quantity']: <8} | {item['display_name']}")
    resp_str = '\n'.join(reqs_table)
    # Handle character limit
    chunks = chunk_response(resp_str)
    await inter.response.send_message(f"```{chunks[0]}```")
    for chunk in chunks[1:]:
        await inter.followup.send(f"```{chunk}```")


# Converts a timestamp to a relative time string (eg. "6 hours ago")
def get_relative_time_str(prev_time):
    if prev_time is None:
        return "Never"
    current_time = time.time()
    elapsed_time = current_time - prev_time

    if elapsed_time < 60:
        return f"{int(elapsed_time)} seconds ago"
    elif elapsed_time < 3600:
        return f"{int(elapsed_time / 60)} minutes ago"
    elif elapsed_time < 86400:
        return f"{int(elapsed_time / 3600)} hours ago"
    else:
        return f"{int(elapsed_time / 86400)} days ago"


# Formats a response string into a list of strings, each with a max length of 1990 characters
# Does not split lines
def chunk_response(table_str):
    chunks = []
    current_chunk = ''
    for line in table_str.split('\n'):
        if len(current_chunk) + len(line) + 1 > 1990:
            chunks.append(current_chunk)
            current_chunk = ''
        current_chunk += line + '\n'
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


# Takes a list of item dicts (w/ 'quantity' & 'info') and sorts into categories & descending order
def organizeItemList(item_list):
    # Sort quotas into categories
    categorized = {}
    for item in item_list:
        db_category = item['info']['category'].split('::')
        if db_category[0] == 'EItemCategory':
            category = db_category[1]
        elif db_category[0] == 'EVehicleProfileType':
            category = 'Vehicle'
        elif db_category[0] == 'Structures':
            category = db_category[0]
        else:
            category = 'Other'
        if category not in categorized:
            categorized[category] = []
        categorized[category].append({'display_name': item['info']['display_name'], 'quantity': item['quantity']})
    # Sort each category by quantity, descending order
    for cat, quotas in categorized.items():
        categorized[cat] = sorted(quotas, key=lambda x: x['quantity'], reverse=True)
    return categorized


bot.run(os.getenv('TOKEN'))