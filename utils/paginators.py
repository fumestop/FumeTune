from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

import discord
from discord.ext.menus import ListPageSource

from .tools import parse_duration
from .player import Player

import config

if TYPE_CHECKING:
    from discord.ext.menus import Menu


class QueuePaginatorSource(ListPageSource):
    def __init__(
        self, entries: list, ctx: discord.Interaction, per_page: Optional[int] = 5
    ):
        super().__init__(entries, per_page=per_page)

        self.ctx: discord.Interaction = ctx

    async def format_page(self, menu: Menu, page: Any) -> discord.Embed:
        player: Player = cast(Player, self.ctx.guild.voice_client)
        channel = player.channel

        embed = discord.Embed(color=config.EMBED_COLOR)
        embed.title = f"Queue | {channel.name}"
        embed.description = "\n".join(
            f"`{_index}`. **[{_track.title}]({_track.uri})** "
            f"({parse_duration(_track.length)} - "
            f"{self.ctx.guild.get_member(_track.extras.requester_id).mention})"
            for _index, _track in page
        )

        total_time = 0

        for track in player.queue:
            total_time += track.length

        embed.set_footer(
            text=f"{len(player.queue)} track(s) in queue | "
            f"{parse_duration(total_time)} total duration"
        )

        return embed

    def is_paginating(self) -> bool:
        return True


class LyricsPaginatorSource(ListPageSource):
    def __init__(
        self,
        entries: list,
        ctx: discord.Interaction,
        title: str,
        artist: str,
        per_page: Optional[int] = 1,
    ):
        super().__init__(entries, per_page=per_page)

        self.ctx = ctx
        self.title = title
        self.artist = artist

    async def format_page(self, menu: Menu, page: Any) -> discord.Embed:
        embed = discord.Embed(color=0xE44C65)
        embed.title = f"Lyrics | {self.title} by {self.artist}"
        embed.description = page

        return embed

    def is_paginating(self) -> bool:
        return True
