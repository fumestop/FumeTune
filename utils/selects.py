from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

import discord
from discord import ui

from .player import Player

if TYPE_CHECKING:
    import wavelink


class TrackSelect(ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Choose the track to play.",
            min_values=1,
            max_values=1,
            options=options,
        )

        self.ctx: Optional[discord.Interaction] = None
        self.tracks: Optional[list[wavelink.Playable]] = None

    async def callback(self, ctx: discord.Interaction):
        if not ctx.user.id == self.ctx.user.id:
            # noinspection PyUnresolvedReferences
            return await ctx.response.send_message(
                f"Only {self.ctx.user.mention} can interact with this message.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        player: Player = cast(Player, self.ctx.guild.voice_client)

        if not self.ctx.user.voice:
            # noinspection PyUnresolvedReferences
            await ctx.response.defer()

            await player.teardown()

            return await self.ctx.edit_original_response(
                content="You are not connected to a voice channel. "
                "Please connect to a voice channel and try again.",
                embed=None,
                view=None,
            )

        track = self.tracks[int(self.values[0]) - 1]

        if track.length > 24 * 60 * 60 * 1000:
            return await self.ctx.edit_original_response(
                content="The track is too long to be played **(>24 hours)**.",
                embed=None,
                view=None,
            )

        track.extras = {"requester_id": self.ctx.user.id}

        await player.queue.put_wait(track)

        if not player.playing:
            await player.do_next()

        return await self.ctx.edit_original_response(
            content="Enqueued! \U0001f44c", embed=None, view=None
        )
