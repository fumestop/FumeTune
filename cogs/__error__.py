import json

import discord
from discord import app_commands
from discord.ext import commands

from utils.tools import parse_cooldown


class Error(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        with open("config.json") as f:
            data = json.load(f)

        self.log_channel_id = data["log_channel_id"]

    async def cog_load(self):
        await self.global_app_command_error_handler(bot=self.bot)

    async def global_app_command_error_handler(self, bot: commands.AutoShardedBot):
        @bot.tree.error
        async def app_command_error(
            ctx: discord.Interaction,
            error: app_commands.AppCommandError,
        ):
            command = ctx.command

            if isinstance(error, app_commands.CommandOnCooldown):
                if ctx.command.name == "lyrics":
                    minutes, seconds = parse_cooldown(error.retry_after)

                    # noinspection PyUnresolvedReferences
                    message = (
                        f"Sorry, you can use this command only **once an hour**. "
                        f"Come back in **{minutes}** minutes and **{seconds}** seconds."
                    )

                else:
                    message = f"You are on cooldown. Please try again in **{round(error.retry_after, 2)}** seconds."

            elif isinstance(error, app_commands.CheckFailure):
                message = str(error)

            else:
                embed = discord.Embed(colour=self.bot.embed_colour)

                embed.title = "Unhandled Exception"
                embed.description = f"```css\n{str(error)}```\nThe error has been reported to the community server. "

                # noinspection PyUnresolvedReferences
                if ctx.response.is_done():
                    # noinspection PyUnresolvedReferences
                    await ctx.edit_original_response(embed=embed)
                else:
                    # noinspection PyUnresolvedReferences
                    await ctx.response.send_message(embed=embed, ephemeral=True)

                embed.description = ""

                embed.add_field(name="Command", value=f"`{command.name}`", inline=False)
                embed.add_field(
                    name="Exception", value=f"```css\n{error.__traceback__}```"
                )

                channel = self.bot.get_channel(self.log_channel_id)

                return await channel.send(embed=embed)

            # noinspection PyUnresolvedReferences
            if ctx.response.is_done():
                # noinspection PyUnresolvedReferences
                await ctx.edit_original_response(content=message)
            else:
                # noinspection PyUnresolvedReferences
                await ctx.response.send_message(content=message, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Error(bot))
