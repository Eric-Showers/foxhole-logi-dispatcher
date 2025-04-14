import discord
from discord import app_commands
from discord.ext import commands

import utils.checks as checks
import utils.helpers as helpers


class Preset(commands.GroupCog, name='preset'):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @app_commands.command(name='create', description='Create a new preset quota')
    @app_commands.describe(preset_name='Name of the preset', quota_list='name:amount, name:amount, ...')
    async def createPreset(self, inter: discord.Interaction, preset_name: str, quota_list:str):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        if quota_list == '':
            await inter.response.send_message('Quota list is empty', ephemeral=True)
            return
        try:
            self.db.createPreset(inter.guild_id, preset_name, quota_list)
        except ValueError as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        await inter.response.send_message(f"Preset {preset_name} created succesfully")

    @app_commands.command(name='edit', description='Edit specific item quotas in a preset')
    @app_commands.describe(preset_name='Name of the preset to edit', quota_list='name:amount, name:amount, ...')
    async def editPreset(self, inter: discord.Interaction, preset_name: str, quota_list: str):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkPreset(self.db, inter, preset_name)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        if quota_list == '':
            await inter.response.send_message('Quota list is empty', ephemeral=True)
            return
        try:
            self.db.editPreset(inter.guild_id, preset_name, quota_list)
        except ValueError as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        await inter.response.send_message(f"Preset {preset_name} edited succesfully")

    @app_commands.command(name='delete', description='Deletes a named preset (does not remove from active quotas)')
    @app_commands.describe(preset_name='Name of the preset')
    async def deletePreset(self, inter: discord.Interaction, preset_name: str):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkPreset(self.db, inter, preset_name)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        try:
            self.db.deletePreset(inter.guild_id, preset_name)
        except ValueError as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        await inter.response.send_message(f"Preset {preset_name} deleted successfully")

    @app_commands.command(name='apply', description='Adds a preset quota to a stockpile (adds to existing quotas)')
    @app_commands.describe(stock_id='Stock ID to apply the preset', preset_name='Name of the preset')
    async def applyPreset(self, inter: discord.Interaction, stock_id: str, preset_name: str):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 2)
            checks.checkStockId(self.db, inter, stock_id)
            checks.checkPreset(self.db, inter, preset_name)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        try:
            self.db.applyPreset(inter.guild_id, stock_id, preset_name)
        except ValueError as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        await inter.response.send_message(f"Preset {preset_name} added to stockpile with id {stock_id}")

    @app_commands.command(name='list', description='List all preset names')
    async def listPresets(self, inter: discord.Interaction):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 1)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        preset_list = self.db.fetchPresets(inter.guild_id)
        if preset_list == []:
            await inter.response.send_message('No presets found for this server', ephemeral=True)
            return
        preset_str = '```Preset Names\n-------------\n{}```'.format('\n'.join(preset_list))
        await inter.response.send_message(preset_str, ephemeral=True)

    @app_commands.command(name='view', description='View the contents of a preset')
    @app_commands.describe(preset_name='Name of the preset')
    async def showPreset(self, inter: discord.Interaction, preset_name: str):
        try:
            checks.checkRegistration(self.db, inter.guild_id)
            checks.checkAccessLevel(self.db, inter, 1)
            checks.checkPreset(self.db, inter, preset_name)
        except discord.app_commands.CheckFailure as e:
            await inter.response.send_message(str(e), ephemeral=True)
            return
        quota_list = self.db.fetchPresetList(inter.guild_id, preset_name)
        categorized = helpers.organizeItemList(quota_list)

        # Build table
        quota_table = ['Category   |  Quantity  | Item Name\n-----------------------------------']
        for cat, quotas in categorized.items():
            quota_table.append(f"{cat: <10} | {quotas[0]['quantity']: <10} | {quotas[0]['display_name']}")
            for q in quotas[1:]:
                quota_table.append(f"{'': <10} | {q['quantity']: <10} | {q['display_name']}")
        resp_str = '\n'.join(quota_table)
        resp_str += '\n\nPreset set string:\n'+', '.join([f"{q['info']['display_name']}:{q['quantity']}" for q in quota_list])

        # Handle overflow
        chunks = helpers.chunk_response(resp_str)
        await inter.response.send_message(f"```{chunks[0]}```", ephemeral=True)
        for chunk in chunks[1:]:
            await inter.followup.send(f"```{chunk}```", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Preset(bot, bot.db))