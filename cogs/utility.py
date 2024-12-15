from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, Optional

import discord
from azapi import AZlyrics
from discord import app_commands
from discord.ext import commands
from discord.ext.menus.views import ViewMenuPages

from utils.cd import cooldown_level_0, cooldown_level_1
from utils.paginators import LyricsPaginatorSource
from utils.tools import parse_duration

if TYPE_CHECKING:
    from bot import FumeTune


class Utility(commands.Cog):
    def __init__(self, bot: FumeTune):
        self.bot: FumeTune = bot

    @app_commands.command(name="lyrics")
    @app_commands.checks.dynamic_cooldown(cooldown_level_1)
    @app_commands.guild_only()
    async def _lyrics(
        self, ctx: discord.Interaction, title: str, artist: Optional[str] = None
    ):
        """Get the lyrics of a song.

        Parameters
        ----------
        title : str
            The title of the song.
        artist : Optional[str]
            The artist of the song.

        """
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        api = AZlyrics("duckduckgo")

        api.title = title
        api.artist = artist if artist else ""

        lyrics = api.getLyrics()

        w = textwrap.TextWrapper(
            width=750, break_long_words=False, replace_whitespace=False
        )

        try:
            entries = w.wrap(text=lyrics)

        except AttributeError:
            return await ctx.edit_original_response(
                content=f"No lyrics found for `{title}`."
            )

        pages = LyricsPaginatorSource(entries=entries, title=api.title, ctx=ctx)
        paginator = ViewMenuPages(
            source=pages,
            timeout=None,
            delete_message_after=False,
            clear_reactions_after=True,
        )

        await ctx.edit_original_response(content="\U0001f44c")
        await paginator.start(ctx)

    @app_commands.command(name="spotify")
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _spotify(self, ctx: discord.Interaction, member: discord.Member):
        """Get Spotify song details from user rich-presence.

        Parameters
        ----------
        member : discord.Member
            The member to get the Spotify song details from.

        """
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        member = ctx.guild.get_member(member.id)

        for activity in member.activities:
            if isinstance(activity, discord.Spotify):
                embed = discord.Embed(color=self.bot.embed_color)
                embed.set_thumbnail(url=activity.album_cover_url)

                embed.add_field(name="Track", value=activity.title)
                embed.add_field(name="Artist", value=activity.artist)
                embed.add_field(name="Album", value=activity.album)
                embed.add_field(
                    name="Started Listening",
                    value=f"<t:{int(activity.created_at.timestamp())}:R>",
                )
                embed.add_field(
                    name="Duration",
                    value=parse_duration(activity.duration.total_seconds() * 1000),
                )
                embed.add_field(
                    name="Track Started",
                    value=f"<t:{int(activity.start.timestamp())}:t>",
                )
                embed.add_field(
                    name="Track Ending",
                    value=f"<t:{int(activity.end.timestamp())}:t>",
                )

                return await ctx.edit_original_response(embed=embed)

        else:
            return await ctx.edit_original_response(
                content=f"`{member.display_name}` is not listening to Spotify right now."
            )


async def setup(bot: FumeTune):
    await bot.add_cog(Utility(bot))
