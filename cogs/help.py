from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils.cd import cooldown_level_0

if TYPE_CHECKING:
    from bot import FumeTune


class Help(commands.Cog):
    def __init__(self, bot: FumeTune):
        self.bot: FumeTune = bot

    @app_commands.command(name="help")
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    async def _help(self, ctx: discord.Interaction):
        """Shows a list of all the commands provided by FumeTune."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        embed = discord.Embed(colour=self.bot.embed_color)
        embed.title = "Command List"
        embed.description = 'Here"s a list of available commands: '

        embed.add_field(
            name="General",
            value=f"`ping`, `uptime`, `web`, `invite`, `vote`, `review`, `community`",
            inline=False,
        )

        embed.add_field(
            name="Music",
            value=f"`play`, `search`, `summon`, `pause`, `resume`, `skip`, `seek`, "
            f"`repeat`, `volume`, `now_playing`, `queue`, `remove`, `flush`, "
            f"`shuffle`, `loop`, `loop_queue`, `stop`, `disconnect`",
            inline=False,
        )

        embed.add_field(
            name="Filters",
            value=f"`filter`, `equalizer`, `channel_mix`",
            inline=False,
        )

        embed.add_field(name="Utility", value=f"`spotify`, `lyrics`", inline=False)

        await ctx.edit_original_response(embed=embed)


async def setup(bot: FumeTune):
    await bot.add_cog(Help(bot))
