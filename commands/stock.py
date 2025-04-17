import asyncio

import discord
from discord import app_commands
from discord.ext import commands

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
        stock_str = '```Stock ID |     Name     |        Town        |      Type      |   Last Updated\n--------------------------------------------------'
        for stock in stockpiles:
            stock_str += "\n{: <8} | {: <12} | {: <18} | {: <14} | {}".format(
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
            checks.checkAccessLevel(self.db, inter, 1)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        item_list = self.db.viewInventory(stock_id)
        categorized = helpers.organizeItemList(item_list)
        # Build response table
        inv_table = ['Category   | Items | Crates | Total | Name\n----------------------------------------']
        for cat, cat_items in categorized.items():
            inv_table.append("{: <10} | {: <5} | {: <6} | {: <5} | {}".format(
                cat,
                cat_items[0].non_crates,
                cat_items[0].crates,
                cat_items[0].getTotal(),
                cat_items[0].display_name
            ))
            for item in cat_items[1:]:
                inv_table.append("{: <10} | {: <5} | {: <6} | {: <5} | {}".format(
                    '',
                    item.non_crates,
                    item.crates,
                    item.getTotal(),
                    item.display_name
                ))
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
            checks.checkAccessLevel(self.db, inter, 1)
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
            checks.checkAccessLevel(self.db, inter, 1)
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

    @app_commands.command(name='status', description='The the current status of a stockpile')
    @app_commands.describe(stock_id='Stock ID of the stockpile to check status', 
                           show_locked='If True will display items that are tech locked (default False)')
    async def status(self, inter: discord.Interaction, stock_id: int, show_locked: bool=False):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 1)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        stock_info, items, quotas, required_amounts = self.db.getStatus(inter.guild_id, stock_id, show_locked)
        if items == []:
            await inter.response.send_message(f"No outstanding requirements found for stock ID {stock_id}", ephemeral=True)
            return
        categorized = helpers.organizeItemList(items)

        # Build response table
        reqs_table = ["({}, {} {}, ID: {}, last updated: {})\n".format(
            stock_info['name'],
            stock_info['town'],
            stock_info['type'],
            stock_id,
            helpers.get_relative_time_str(stock_info['last_update'])
        )]
        reqs_table.append('Category   | Inventory | Quota | Amount Needed | %Full | Item Name\n-----------------------------------------------------------------')
        for cat, cat_items in categorized.items():
            if cat_items[0].category in ['Vehicles', 'Structures']:
                inventory = cat_items[0].getTotal()
            else:
                inventory = cat_items[0].crates
            reqs_table.append("{: <10} | {: <9} | {: <5} | {: <13} | {: >4.0f}% | {}".format(
                cat,
                inventory,
                quotas[cat_items[0].display_name],
                required_amounts[cat_items[0].display_name],
                (inventory / quotas[cat_items[0].display_name]) * 100,
                cat_items[0].display_name
            ))
            for item in cat_items[1:]:
                if item.category in ['Vehicles', 'Structures']:
                    inventory = item.getTotal()
                else:
                    inventory = item.crates
                reqs_table.append("{: <10} | {: <9} | {: <5} | {: <13} | {: >4.0f}% | {}".format(
                    '',
                    inventory,
                    quotas[item.display_name],
                    required_amounts[item.display_name],
                    (inventory / quotas[item.display_name]) * 100,
                    item.display_name
                ))
        resp_str = '\n'.join(reqs_table)
        # Handle character limit
        chunks = helpers.chunk_response(resp_str)
        await inter.response.send_message(f"```{chunks[0]}```", ephemeral=True)
        for chunk in chunks[1:]:
            await inter.followup.send(f"```{chunk}```", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Stock(bot, bot.db))