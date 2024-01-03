import json
import string
import random
import traceback

import discord
from discord import app_commands
from discord.ext import commands


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
            if isinstance(error, app_commands.CheckFailure):
                return

            if isinstance(error, app_commands.CommandOnCooldown):
                message = f"You are on cooldown. Please try again in **{round(error.retry_after, 2)}** seconds."

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

                embed.add_field(
                    name="Command", value=f"`{ctx.command.name}`", inline=False
                )
                embed.add_field(
                    name="Server",
                    value=f"**{ctx.guild.name}** `({ctx.guild.id})`",
                    inline=False,
                )

                file_name = (
                    f"logs/error-{ctx.guild.id}-{ctx.command.name}-"
                    f"{''.join(random.choices(string.ascii_letters + string.digits, k=10))}.log"
                )

                with open(file_name, "w") as f:
                    f.write("".join(traceback.format_exception(error)))

                embed.add_field(
                    name="Log",
                    value=f"Saved to `{file_name}`",
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
