import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import utils.checks as checks
import utils.helpers as helpers
from views.items import FactionSelectView


class Item(commands.GroupCog, name='item'):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @app_commands.command(name='menu')
    async def menu(self, inter: discord.Interaction):
        await inter.response.send_message(
            "Select a faction to begin browsing items:",
            view=FactionSelectView(self.bot.db),
            ephemeral=True
        )

    @app_commands.command(name='tech', description='Set an item\'s tech status ')
    @app_commands.describe(item_list='In-game names of the items to lock/unlock: name1, name2, ... ', is_locked='True or False')
    async def tech(self, inter: discord.Interaction, item_list: str, is_locked: bool):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        try:
            self.db.setTechLock(inter.guild_id, item_list, is_locked)
        except ValueError as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        await inter.response.send_message(f"Tech status updated", ephemeral=True)

    
    @app_commands.command(name='showlocked', description='Show tech locked items')
    async def showlocked(self, inter: discord.Interaction):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 1)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        
        item_list = self.db.fetchLockedItems(inter.guild_id)
        if item_list == []:
            await inter.response.send_message('No locked items found', ephemeral=True)
            return
        
        categorized = helpers.organizeItemList(item_list)
        locks_table = ['Category   | Item Name\n-----------------------------------']
        for cat, cat_items in categorized.items():
            locks_table.append(f"{cat: <10} | {cat_items[0]['display_name']}")
            for item in cat_items[1:]:
                locks_table.append(f"{'': <10} | {item['display_name']}")
        resp_str = '\n'.join(locks_table)
        # Handle character limit
        chunks = helpers.chunk_response(resp_str)
        await inter.response.send_message(f"```{chunks[0]}```")
        for chunk in chunks[1:]:
            await inter.followup.send(f"```{chunk}```")
        
        

        

async def setup(bot):
    await bot.add_cog(Item(bot, bot.db))