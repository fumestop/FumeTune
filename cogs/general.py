import math
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.tools import dynamic_cooldown_x


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Returns the API and bot latency")
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    async def _ping(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        embed = discord.Embed(colour=self.bot.embed_colour)
        embed.description = "**Pong!**"

        ms = self.bot.latency * 1000

        embed.add_field(name="API latency (Heartbeat)", value=f"`{int(ms)} ms`")

        t1 = datetime.utcnow().strftime("%f")

        await ctx.edit_original_response(embed=embed)

        t2 = datetime.utcnow().strftime("%f")
        diff = int(math.fabs((int(t2) - int(t1)) / 1000))

        embed.add_field(name="Bot latency (Round-trip)", value=f"`{diff} ms`")

        await ctx.edit_original_response(embed=embed)

    @app_commands.command(name="web", description="Shows web resources about FumeStop.")
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    async def _web(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Website", url="https://fumes.top/"))
        view.add_item(
            discord.ui.Button(label="Homepage", url="https://fumes.top/fumetune")
        )
        view.add_item(
            discord.ui.Button(label="Twitter", url="https://twitter.com/fumestop")
        )

        await ctx.edit_original_response(
            content="Here are the links to various FumeStop resources on the web:",
            view=view,
        )

    @app_commands.command(
        name="invite", description="Shows the link to invite the bot to your server."
    )
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    async def _invite(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="With Required Permissions (Customizable)",
                url="https://fumes.top/fumetune/invite",
            )
        )
        view.add_item(
            discord.ui.Button(
                label="With Administrator Permissions",
                url="https://fumes.top/fumetune/invite?admin=true",
            )
        )

        await ctx.edit_original_response(
            content="Thank you for choosing me!", view=view
        )

    @app_commands.command(
        name="vote", description="Shows the URL to vote for FumeStop on Top.GG!"
    )
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    async def _vote(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(label="Vote", url="https://top.gg/bot/123456789")
        )

        await ctx.edit_original_response(
            content="Thank you for voting for me!", view=view
        )

    @app_commands.command(
        name="community",
        description="Sends the invite to the official community server.",
    )
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    async def _community(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Community Server Invite", url="https://fumes.top/community"
            )
        )

        await ctx.edit_original_response(
            content="Join the community server for help & updates!", view=view
        )


async def setup(bot):
    await bot.add_cog(General(bot))
