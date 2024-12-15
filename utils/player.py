from __future__ import annotations

import asyncio

import async_timeout
import discord
import wavelink

from utils.tools import parse_duration


class Player(wavelink.Player):
    def __init__(self, ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ctx: discord.Interaction = ctx

        self.dj: discord.Member = self.ctx.user

        self.queue: wavelink.Queue = wavelink.Queue()

        self.waiting: bool = False
        self.loop: bool = False
        self.loop_queue: bool = False

        self.pause_votes: set = set()
        self.resume_votes: set = set()
        self.skip_votes: set = set()
        self.seek_votes: set = set()
        self.shuffle_votes: set = set()
        self.stop_votes: set = set()

    async def do_next(self):
        if self.playing or self.waiting:
            return

        self.pause_votes.clear()
        self.resume_votes.clear()
        self.skip_votes.clear()
        self.shuffle_votes.clear()
        self.stop_votes.clear()

        try:
            self.waiting = True

            with async_timeout.timeout(300):
                track = await self.queue.get_wait()

        except asyncio.TimeoutError:
            return await self.teardown()

        await self.play(track, volume=100)

        self.waiting = False

        embed, view = self.build_track_embed()

        try:
            await self.ctx.channel.send(embed=embed, view=view)

        except (discord.Forbidden, discord.errors.Forbidden):
            return

    def build_track_embed(self):
        track = self.current

        channel = self.channel

        embed = discord.Embed(title=f"Now Playing | {channel.name}", colour=0xE44C65)
        embed.description = f"```\n{track.title}```\n\n"

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        embed.add_field(name="Author", value=track.author)
        embed.add_field(name="Duration", value=f"`{parse_duration(track.length)}`")
        embed.add_field(name="Queue Length", value=len(self.queue))
        embed.add_field(name="Volume", value=f"**`{self.volume}%`**")
        embed.add_field(
            name="Requested By",
            value=self.ctx.guild.get_member(track.extras.requester_id).mention,
        )

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Video Link", url=track.uri))

        return embed, view

    async def teardown(self):
        self.queue.clear()

        self.loop = False
        self.loop_queue = False

        await self.stop(force=True)
        await self.disconnect()
