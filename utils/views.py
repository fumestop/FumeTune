from __future__ import annotations
from typing import TYPE_CHECKING, Optional, cast

import discord
from discord import ui

from .player import Player

if TYPE_CHECKING:
    import wavelink


class TrackConfirm(ui.View):
    def __init__(self):
        super().__init__(timeout=1 * 60)

        self.ctx: Optional[discord.Interaction] = None

    # noinspection PyUnusedLocal
    @discord.ui.button(emoji="\U0001F6AB")
    async def _cancel(self, ctx: discord.Interaction, button: discord.ui.Button):
        if not ctx.user.id == self.ctx.user.id:
            # noinspection PyUnresolvedReferences
            return await ctx.response.send_message(
                f"Only {self.ctx.user.mention} can interact with this message.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        self.stop()

        # noinspection PyUnresolvedReferences
        await self.ctx.response.send_message(
            content="The action was successfully cancelled!", embed=None, view=None
        )

    async def on_timeout(self):
        await self.ctx.edit_original_response(
            content="Timeout! Please try again.", embed=None, view=None
        )


class PlaylistConfirm(ui.View):
    def __init__(self):
        super().__init__(timeout=1 * 60)

        self.ctx: Optional[discord.Interaction] = None
        self.playlist: Optional[wavelink.Playlist] = None

    # noinspection PyUnusedLocal
    @discord.ui.button(emoji="\u2705")
    async def _confirm(self, ctx: discord.Interaction, button: discord.ui.Button):
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

            return self.ctx.edit_original_response(
                content="You are not connected to a voice channel. "
                "Please connect to a voice channel and try again.",
                embed=None,
                view=None,
            )

        if any(track.length > 24 * 60 * 60 * 1000 for track in self.playlist.tracks):
            return await ctx.edit_original_response(
                content="Sorry, one or more songs are too long to be played **(>24 hours)**."
            )

        self.playlist.extras = {"requester_id": ctx.user.id}
        await player.queue.put_wait(self.playlist)

        if not player.playing:
            await player.do_next()

        self.stop()

        # noinspection PyUnresolvedReferences
        await ctx.response.defer()
        # noinspection PyUnresolvedReferences
        await self.ctx.edit_original_response(
            content="Enqueued! \U0001F44C", embed=None, view=None
        )

    # noinspection PyUnusedLocal
    @discord.ui.button(emoji="\U0001F6AB")
    async def _cancel(self, ctx: discord.Interaction, button: discord.ui.Button):
        if not ctx.user.id == self.ctx.user.id:
            # noinspection PyUnresolvedReferences
            return await ctx.response.send_message(
                f"Only {self.ctx.user.mention} can interact with this message.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        await self.ctx.edit_original_response(
            content="The action was successfully cancelled!", embed=None, view=None
        )

    async def on_timeout(self):
        await self.ctx.edit_original_response(
            content="Timeout! Please try again.", embed=None, view=None
        )
