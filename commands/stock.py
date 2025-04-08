import discord
from discord import app_commands
from discord.ext import commands
import asyncio

import utils.checks as checks
import utils.helpers as helpers


class Stock(commands.GroupCog, name='stock'):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @app_commands.command(name='list', description='List all stockpiles registered on the discord server')
    async def list(self, inter: discord.Interaction):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 1)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        
        stockpiles = self.db.fetchStockpiles(inter.guild_id)
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
                helpers.get_relative_time_str(stock['last_update'])
            )
        stock_str += '```'
        await inter.response.send_message(stock_str)


    @app_commands.command(name='create', description='Add a new stockpile in the bot')
    @app_commands.describe(
        town='Town that the stockpile is in (nearest major label)', 
        type='Seaport or Storage Depot',
        name='In-game name of the stockpile'
    )
    async def create(self, inter: discord.Interaction, town: str, type: str, name: str):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 1)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        try:
            self.db.create(inter.guild_id, town, type, name)
        except ValueError as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        await inter.response.send_message(f"Created stockpile named {name} at the {type} in {town}")

    @app_commands.command(name='delete', description='Delete a stockpile from the bot')
    @app_commands.describe(stock_id='Stock ID to delete')
    async def delete(self, inter: discord.Interaction, stock_id: int):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        self.db.delete(stock_id)
        await inter.response.send_message(f"Deleted stockpile with ID {stock_id}")

    @app_commands.command(name='view', description='View the contents of a stockpile')
    @app_commands.describe(stock_id='Stock ID to view')
    async def view(self, inter: discord.Interaction, stock_id: int):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        item_list = self.db.viewInventory(stock_id)
        categorized = helpers.organizeItemList(item_list)
        # Build response table
        inv_table = ['Category   | Quantity | Item Name\n-----------------------------------']
        for cat, cat_items in categorized.items():
            inv_table.append(f"{cat: <10} | {cat_items[0]['quantity']: <8} | {cat_items[0]['display_name']}")
            for item in cat_items[1:]:
                inv_table.append(f"{'': <10} | {item['quantity']: <8} | {item['display_name']}")
        resp_str = '\n'.join(inv_table)
        # Handle character limit
        chunks = helpers.chunk_response(resp_str)
        await inter.response.send_message(f"```{chunks[0]}```")
        for chunk in chunks[1:]:
            await inter.followup.send(f"```{chunk}```")

    @app_commands.command(name='set', description='Set the inventory of a stockpile using a list of item amounts')
    @app_commands.describe(
        stock_id='Stock ID to update', 
        crates_list='name:amount, name:amount, ... (name must match in-game name)',
        non_crates_list='name:amount, name:amount, ... (only use for vehicles/structures)'
    )
    async def set(self, inter: discord.Interaction, stock_id: int, crates_list: str='', non_crates_list: str=''):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        if crates_list == '' and non_crates_list == '':
            await inter.response.send_message('crates_list and non_crates_list cannot both be empty', ephemeral=True)
            return
        try:
            self.db.setInventory(stock_id, crates_list, non_crates_list)
        except ValueError as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        await inter.response.send_message(f"Stock ID {stock_id} inventory has been updated")


    @app_commands.command(name='update', description='Update the inventory of a stockpile using a screenshot')
    @app_commands.describe(stock_id='Stock ID to update')
    async def update(self, inter: discord.Interaction, stock_id: int):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        
        # Prompt user for screenshot
        await inter.response.send_message("Please reply with your screenshot.")
        def check(msg):
            return (
                msg.author == inter.user 
                and msg.channel == inter.channel
                and msg.attachments
            )
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=60)  # Wait for 60s
        except asyncio.TimeoutError:
            await inter.followup.send("File upload timed out.", ephemeral=True)
            return

        # Ingest screenshot
        attachment = msg.attachments[0]
        media, file_type = attachment.content_type.split('/')
        if 'image' not in media:
            await inter.followup.send(f"Error: File must be an image, not {attachment.content_type}", ephemeral=True)
            return
        screenshot = await attachment.read()
        temp_path = f"temp/{inter.id}.{file_type}"
        with open(temp_path, 'xb') as outfile:
            outfile.write(screenshot)
        # Send screenshot to FIR to parse into TSV
        try:
            tsv_data = await helpers.run_fir_parser(temp_path)
        except asyncio.TimeoutError as e:
            await inter.followup.send(str(e), ephemeral=True)
            return
        # Update DB
        try:
            self.db.updateInventory(stock_id, tsv_data.splitlines())
        except ValueError as e:
            await inter.followup.send(str(e), ephemeral=True)
            return
        await inter.followup.send('Updated stockpile with ID {}'.format(stock_id))

    @app_commands.command(name='updatemulti', description='Update the inventory of multiple stockpiles using a TSV file')
    @app_commands.describe(stock_ids='1, 3, 4, ...')
    async def updateMulti(self, inter: discord.Interaction, stock_ids: str):
        stock_ids = [int(id.strip()) for id in stock_ids.split(',')]
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            for id in stock_ids:
                checks.checkStockId(self.db, inter, id)
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
            msg = await self.bot.wait_for("message", check=check, timeout=60)  # Wait for 60s
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
            stock_ids = self.db.updateMulti(stock_ids, tsvFile)
        except ValueError as e:
            await inter.followup.send(str(e), ephemeral=True)
            return
        await inter.followup.send(f"Updated stockpiles with IDs {stock_ids}")


async def setup(bot):
    await bot.add_cog(Stock(bot, bot.db))