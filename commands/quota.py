import discord
from discord import app_commands
from discord.ext import commands

import utils.checks as checks
import utils.helpers as helpers


class Quota(commands.GroupCog, name='quota'):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @app_commands.command(name='set', description='Sets the quotas for the specified items on a stockpile (overwrites)')
    @app_commands.describe(stock_id='Stock ID to set quotas on', quota_list='name:amount, name:amount, ...')
    async def set(self, inter: discord.Interaction, stock_id: int, quota_list: str):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        try:
            self.db.addQuotas(stock_id, quota_list)
        except ValueError as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        await inter.response.send_message(f"Added quotas to stockpile with ID {stock_id}", ephemeral=True)


    @app_commands.command(name='delete', description='Removes all quotas for a stockpile.')
    @app_commands.describe(stock_id='Stock ID to delete quotas from')
    async def delete(self, inter: discord.Interaction, stock_id: int):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        self.db.deleteQuotas(stock_id)
        await inter.response.send_message(f"Deleted quotas for stockpile with ID {stock_id}", ephemeral=True)

    @app_commands.command(name='view', description='View the quotas that are set on a stockpile')
    @app_commands.describe(stock_id='Stock ID to view quotas on')
    async def view(self, inter: discord.Interaction, stock_id: int):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 1)
            checks.checkStockId(self.db, inter, stock_id)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        item_list = self.db.fetchQuotas(stock_id)
        if item_list == []:
            await inter.response.send_message(f"No quotas found on stock ID {stock_id}", ephemeral=True)
            return
        
        # Build table
        categorized = helpers.organizeItemList(item_list)
        quota_table = ['  #  | Item Name']
        for cat, quotas in categorized.items():
            quota_table.append(f"{cat:_^20}")
            for q in quotas:
                quota_table.append(f"{q.crates: <4} | {q.display_name}")
        resp_str = '\n'.join(quota_table)
        resp_str += '\n\nQuota set string:\n'+', '.join([f"{q.display_name}:{q.crates}" for q in item_list])
        
        # Handle overflow
        chunks = helpers.chunk_response(resp_str)
        await inter.response.send_message(f"```\n{chunks[0]}```", ephemeral=True)
        for chunk in chunks[1:]:
            await inter.followup.send(f"```\n{chunk}```", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Quota(bot, bot.db))