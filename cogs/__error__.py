from __future__ import annotations

import random
import string
import traceback
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from bot import FumeTune


class Error(commands.Cog):
    def __init__(self, bot: FumeTune):
        self.bot: FumeTune = bot

    async def cog_load(self):
        await self.global_app_command_error_handler(bot=self.bot)

    async def global_app_command_error_handler(self, bot: commands.AutoShardedBot):
        @bot.tree.error
        async def app_command_error(
            ctx: discord.Interaction,
            error: app_commands.AppCommandError,
        ):
            if isinstance(
                error,
                (
                    app_commands.CommandOnCooldown,
                    app_commands.errors.CommandOnCooldown,
                ),
            ):
                message = f"You are on cooldown. Please try again in **{round(error.retry_after, 2)}** seconds."

            elif isinstance(error, app_commands.errors.CheckFailure):
                message = error.__str__()

            elif (
                isinstance(error, app_commands.errors.CommandInvokeError)
                and "InvalidNodeException" in error.__str__()
            ):
                message = "No music node is currently available to serve your request. Please try again later."

            else:
                embed = discord.Embed(color=self.bot.embed_color)

                embed.title = "Oops! Something went wrong."
                embed.description = (
                    f"```css\n{error.__str__()}```"
                    f"\nThe error has been reported to the community server. "
                )

                # noinspection PyUnresolvedReferences
                if ctx.response.is_done():
                    # noinspection PyUnresolvedReferences
                    await ctx.edit_original_response(embed=embed)
                else:
                    # noinspection PyUnresolvedReferences
                    await ctx.response.send_message(embed=embed, ephemeral=True)

                embed.title = "Error Report"
                embed.description = ""

                embed.add_field(
                    name="Command", value=f"`{ctx.command.name}`", inline=False
                )
                embed.add_field(
                    name="Server",
                    value=f"**{ctx.guild.name}** `({ctx.guild.id})`",
                    inline=False,
                )

                file_name = (
                    f"logs/errors/{ctx.guild.id}-{ctx.command.name}-"
                    f"{''.join(random.choices(string.ascii_letters + string.digits, k=10))}.log"
                )

                with open(file_name, "w") as f:
                    f.write("".join(traceback.format_exception(error)))

                embed.add_field(
                    name="Log",
                    value=f"Saved to `{file_name}`",
                )

                return await self.bot.webhook.send(embed=embed)

            # noinspection PyUnresolvedReferences
            if ctx.response.is_done():
                # noinspection PyUnresolvedReferences
                try:
                    await ctx.edit_original_response(content=message, view=None)

                except (discord.NotFound, discord.errors.NotFound):
                    await ctx.followup.send(content=message, ephemeral=True, view=None)
            else:
                # noinspection PyUnresolvedReferences
                await ctx.response.send_message(
                    content=message, ephemeral=True, view=None
                )


async def setup(bot: FumeTune):
    await bot.add_cog(Error(bot))
