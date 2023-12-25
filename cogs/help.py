import discord
from discord import app_commands
from discord.ext import commands

from utils.tools import dynamic_cooldown_x


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="help", description="A list of all the commands provided by FumeTune."
    )
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    async def _help(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        embed = discord.Embed(colour=self.bot.embed_colour)

        embed.title = "Command List"

        embed.description = "Here's a list of available commands: "

        embed.add_field(
            name="General",
            value=f"`ping`, `web`, `invite`, `vote`, `community`",
            inline=False,
        )

        embed.add_field(
            name="Music",
            value=f"`summon`, `search`, `play`, `pause`, `resume`, `skip`, `seek`, `volume`, `np`, "
            f" `queue`, `flush`, `remove`, `shuffle`, `loop`, `loop_queue`, `repeat`, `stop`, "
            f"`disconnect`",
            inline=False,
        )

        embed.add_field(
            name="Filters",
            value=f"`filter`, `equalizer`, `channel_mix`",
            inline=False,
        )

        embed.add_field(name="Utility", value=f"`spotify`, `lyrics`", inline=False)

        await ctx.edit_original_response(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
