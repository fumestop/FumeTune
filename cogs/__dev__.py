import json

import discord
from discord import app_commands
from discord.ext import commands


with open("config.json") as json_file:
    data = json.load(json_file)
    community_server_id = data["community_server_id"]


class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="load", description="Load an extension.")
    @app_commands.guilds(community_server_id)
    async def _load(self, ctx: discord.Interaction, extension: str):
        # noinspection PyUnresolvedReferences
        await ctx.response.defecr(thinking=True)

        if not await self.bot.is_owner(ctx.user):
            return await ctx.edit_original_response(
                content="This is an owner(s) only command!"
            )

        try:
            await self.bot.load_extension(f"cogs.{extension}")

        except commands.ExtensionNotFound:
            return await ctx.edit_original_response(
                content="Sorry, no such extension found."
            )

        except commands.ExtensionAlreadyLoaded:
            return await ctx.edit_original_response(
                content="Sorry, this extension is already loaded."
            )

        await ctx.edit_original_response(content="The extension has been loaded.")

    @app_commands.command(name="unload", description="Unload an extension.")
    @app_commands.guilds(community_server_id)
    async def _unload(self, ctx: discord.Interaction, extension: str):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        if not await self.bot.is_owner(ctx.user):
            return await ctx.edit_original_response(
                content="This is an owner(s) only command!"
            )

        try:
            await self.bot.unload_extension(f"cogs.{extension}")

        except commands.ExtensionNotLoaded:
            return await ctx.edit_original_response(
                content="Sorry, no such extension is loaded."
            )

        await ctx.edit_original_response(content="The extension has been unloaded.")

    @app_commands.command(name="reload")
    @app_commands.guilds(community_server_id)
    async def _reload(self, ctx: discord.Interaction, extension: str):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        if not await self.bot.is_owner(ctx.user):
            return await ctx.edit_original_response(
                content="This is an owner(s) only command!"
            )

        try:
            await self.bot.reload_extension(f"cogs.{extension}")

        except commands.ExtensionNotLoaded:
            return await ctx.edit_original_response(
                content="Sorry, no such extension is loaded."
            )

        await ctx.edit_original_response(content="The extension has been reloaded.")

    @app_commands.command(name="sync")
    @app_commands.guilds(community_server_id)
    async def _sync(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        if not await self.bot.is_owner(ctx.user):
            return await ctx.edit_original_response(
                content="This is an owner(s) only command!"
            )

        await self.bot.tree.sync()
        await self.bot.tree.sync(guild=discord.Object(id=community_server_id))
        self.bot.tree.copy_global_to(guild=discord.Object(id=community_server_id))

        await ctx.edit_original_response(content="Synced.")


async def setup(bot):
    await bot.add_cog(Dev(bot))
