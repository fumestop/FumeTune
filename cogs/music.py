import math
import json
import string
import random
import asyncio
import textwrap
import collections
from typing import cast

import discord
from discord import ui, app_commands
from discord.ext import commands
from discord.ext.menus import Menu, ListPageSource
from discord.ext.menus.views import ViewMenuPages

import wavelink
import async_timeout
from azapi import AZlyrics

from utils.tools import (
    parse_duration,
    dynamic_cooldown_x,
    dynamic_cooldown_y,
)


class Player(wavelink.Player):
    def __init__(self, ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ctx: discord.Interaction = ctx

        self.dj: discord.Member = self.ctx.user

        self.queue = wavelink.Queue()

        self.waiting = False
        self.loop = False
        self.loop_queue = False

        self.pause_votes = set()
        self.resume_votes = set()
        self.skip_votes = set()
        self.seek_votes = set()
        self.shuffle_votes = set()
        self.stop_votes = set()

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
        embed.description = f"```css\n{track.title}```\n\n"

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        embed.add_field(name="Author", value=track.author)
        embed.add_field(name="Duration", value=parse_duration(track.length))
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
        await self.stop(force=True)
        await self.disconnect()


class QueuePaginatorSource(ListPageSource):
    def __init__(self, entries, ctx, per_page=5):
        self.ctx: discord.Interaction = ctx
        super().__init__(entries, per_page=per_page)

    async def format_page(self, menu: Menu, page):
        player: Player = cast(Player, self.ctx.guild.voice_client)
        channel = player.channel

        embed = discord.Embed(title=f"Queue | {channel.name}", colour=0xE44C65)
        embed.description = "\n".join(
            f"`{index}`. **[{track.title}]({track.uri})** "
            f"({parse_duration(track.length)} - "
            f"{self.ctx.guild.get_member(track.extras.requester_id).mention})"
            for index, track in page
        )

        total_time = 0

        for track in player.queue:
            total_time += track.length

        total_time = parse_duration(total_time)

        embed.description += f"\n\n**{len(player.queue)} song(s) in queue | {total_time} total duration**"

        return embed

    def is_paginating(self):
        return True


class LyricsPaginatorSource(ListPageSource):
    def __init__(self, entries, title, ctx, per_page=1):
        self.ctx = ctx
        self.title = title
        super().__init__(entries, per_page=per_page)

    async def format_page(self, menu: Menu, page):
        embed = discord.Embed(title=f"Lyrics | {self.title}", colour=0xE44C65)
        embed.description = page
        return embed

    def is_paginating(self):
        return True


class FilterModal(ui.Modal, title="Filter Parameters"):
    interaction: discord.Interaction = None

    async def on_submit(self, ctx: discord.Interaction):
        self.interaction = ctx

        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)


class PlaylistConfirm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

        self.ctx = None
        self.playlist = None

    # noinspection PyUnusedLocal
    @discord.ui.button(emoji="\u2705")
    async def _confirm(self, ctx: discord.Interaction, button: discord.ui.Button):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer()

        player: Player = cast(Player, self.ctx.guild.voice_client)

        if not self.ctx.user.voice:
            await player.teardown()

            return self.ctx.edit_original_response(
                content="You are not connected to a voice channel. "
                "Please connect to a voice channel and try again.",
                embed=None,
                view=None,
            )

        for track in self.playlist:
            track.extras = {"requester_id": ctx.user.id}
            await player.queue.put_wait(track)

        if not player.playing:
            await player.do_next()

        return await self.ctx.edit_original_response(
            content="Enqueued! \U0001F44C", embed=None, view=None
        )

    # noinspection PyUnusedLocal
    @discord.ui.button(emoji="\U0001F6AB")
    async def _cancel(self, ctx: discord.Interaction, button: discord.ui.Button):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer()

        await self.ctx.edit_original_response(
            content="The action was successfully cancelled!", embed=None, view=None
        )

    async def on_timeout(self):
        await self.ctx.edit_original_response(
            content="Timeout! Please try again.", embed=None, view=None
        )


class TrackConfirm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

        self.ctx = None

    # noinspection PyUnusedLocal
    @discord.ui.button(emoji="\U0001F6AB")
    async def _cancel(self, ctx: discord.Interaction, button: discord.ui.Button):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer()

        await self.ctx.edit_original_response(
            content="The action was successfully cancelled!", embed=None, view=None
        )

    async def on_timeout(self):
        await self.ctx.edit_original_response(
            content="Timeout! Please try again.", embed=None, view=None
        )


class TrackSelect(discord.ui.Select):
    def __init__(self, options):
        self.ctx = None
        self.tracks = None

        super().__init__(
            placeholder="Choose the track to play.",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer()

        player: Player = cast(Player, self.ctx.guild.voice_client)

        if not self.ctx.user.voice:
            await player.teardown()

            return self.ctx.edit_original_response(
                content="You are not connected to a voice channel. "
                "Please connect to a voice channel and try again.",
                embed=None,
                view=None,
            )

        track = self.tracks[int(self.values[0]) - 1]
        track.extras = {"requester_id": self.ctx.user.id}

        await player.queue.put_wait(track)

        if not player.playing:
            await player.do_next()

        return await self.ctx.edit_original_response(
            content="Enqueued! \U0001F44C", embed=None, view=None
        )


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        with open("config.json") as f:
            data = json.load(f)

        self.log_channel_id = data["log_channel_id"]

        self.bot.loop.create_task(self.connect_nodes())

    async def connect_nodes(self):
        await self.bot.wait_until_ready()

        with open("config.json") as f:
            data = json.load(f)

        nodes = list()

        for node in data["nodes"]:
            nodes.append(
                wavelink.Node(
                    identifier=node["identifier"],
                    uri=f"{'http' if node['ssl'] is False else 'https'}://{node['host']}:{node['port']}",
                    password=node["password"],
                )
            )

        await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=None)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        self.bot.log.info(f"Music node {payload.node.identifier} is ready")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(
        self, payload: wavelink.TrackExceptionEventPayload
    ):
        player: Player | None = payload.player

        if not player:
            return

        await player.do_next()

        await player.channel.send(
            content="The song encountered an error, **it is being skipped.**"
        )

        embed = discord.Embed(colour=self.bot.embed_colour)
        embed.description = ""

        embed.add_field(name="Track", value=f"`{payload.track.title}`", inline=False)

        # noinspection PyUnresolvedReferences
        exception = {
            "title": payload.track.title,
            "source": payload.track.source,
            "severity": payload.exception.severity,
            "cause": payload.exception.cause,
            "message": payload.exception.message,
        }

        file_name = (
            f"logs/tracks/{payload.track.identifier}"
            f"{''.join(random.choices(string.ascii_letters + string.digits, k=10))}.log"
        )

        with open(file_name, "w") as f:
            json.dump(exception, f, indent=4)

        embed.add_field(
            name="Log",
            value=f"Saved to `{file_name}`",
        )

        channel = self.bot.get_channel(self.log_channel_id)

        return await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload):
        player: Player | None = payload.player

        if not player:
            return

        # noinspection PyProtectedMember
        player.queue._queue.insert(0, payload.track)
        await player.do_next()

        await player.channel.send(
            content="The song got stuck, **it is being replayed.**"
        )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: Player | None = payload.player

        if not player:
            return

        if player.loop:
            # noinspection PyProtectedMember
            player.queue._queue.insert(0, payload.original)

        elif player.loop_queue:
            await player.queue.put_wait(payload.original)

        await player.do_next()

    # noinspection PyUnusedLocal
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return

        player: Player = cast(Player, member.guild.voice_client)

        if not player or not player.connected:
            return

        if not player.channel or not player.ctx:
            await player.teardown()

        channel = player.channel

        if len(channel.members) == 1:
            await player.teardown()

        if member == player.dj and after.channel is None:
            for m in channel.members:
                if m.bot:
                    continue
                else:
                    player.dj = m
                    return

        elif after.channel == channel and player.dj not in channel.members:
            player.dj = member

    @staticmethod
    async def _playable_checks(ctx: discord.Interaction):
        player: Player = cast(Player, ctx.guild.voice_client)

        if not player:
            channel = ctx.user.voice.channel

            if (
                not channel.permissions_for(ctx.guild.me).connect
                or not channel.permissions_for(ctx.guild.me).speak
            ):
                raise app_commands.CheckFailure(
                    "Sorry, I do not have permissions to `Connect` and/or `Speak` in that voice channel."
                )

            if channel.user_limit and len(channel.members) == channel.user_limit:
                raise app_commands.CheckFailure("Sorry, that voice channel is full.")

            if not ctx.channel.permissions_for(ctx.guild.me).send_messages:
                raise app_commands.CheckFailure(
                    "Sorry, I do not have permissions to send messages in this channel."
                )

            pl = Player(ctx=ctx)

            try:
                _: Player = await channel.connect(cls=pl, timeout=10.0)

            except wavelink.exceptions.ChannelTimeoutException:
                raise app_commands.CheckFailure(
                    "I was unable to connect to that voice channel."
                )

        return True

    @staticmethod
    def _initial_checks(ctx: discord.Interaction):
        if not ctx.user.voice or not ctx.user.voice.channel:
            raise app_commands.CheckFailure("Please join a voice channel first.")

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return True

        if player.ctx and player.ctx.channel != ctx.channel:
            raise app_commands.CheckFailure(
                f"{ctx.user.mention}, you must be in {player.ctx.channel.mention} "
                f"for this session."
            )

        if Music.is_privileged(ctx):
            return True

        if player.connected:
            if ctx.user not in player.channel.members:
                raise app_commands.CheckFailure(
                    f"You must be connected to `{player.channel.name}`."
                )

        return True

    @staticmethod
    def required(ctx: discord.Interaction):
        player: Player = cast(Player, ctx.guild.voice_client)
        channel = player.channel
        required = math.ceil((len(channel.members) - 1) / 2.5)

        if ctx.command.name == "stop":
            if len(channel.members) == 3:
                required = 2

        return required

    @staticmethod
    def is_privileged(ctx: discord.Interaction):
        player: Player = cast(Player, ctx.guild.voice_client)

        return (
            player.dj == ctx.user
            or ctx.user.guild_permissions.manage_guild
            or "dj" in [role.name.lower() for role in ctx.user.roles]
        )

    @app_commands.command(name="lyrics", description="Get the lyrics of a song.")
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_y)
    @app_commands.guild_only()
    async def _lyrics(self, ctx: discord.Interaction, title: str, artist: str = None):
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

        await ctx.edit_original_response(content="\U0001F44C")
        await paginator.start(ctx)

    @app_commands.command(
        name="spotify", description="Get Spotify song details from user rich-presence."
    )
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _spotify(self, ctx: discord.Interaction, member: discord.Member):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        member = ctx.guild.get_member(member.id)

        for activity in member.activities:
            if isinstance(activity, discord.Spotify):
                embed = discord.Embed(color=self.bot.embed_colour)
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
                    name="Track Ending", value=f"<t:{int(activity.end.timestamp())}:t>"
                )

                return await ctx.edit_original_response(embed=embed)

        else:
            return await ctx.edit_original_response(
                content=f"`{member.display_name}` is not listening to Spotify right now."
            )

    @app_commands.command(
        name="summon", description="Summon the bot to a voice channel."
    )
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _summon(
        self, ctx: discord.Interaction, channel: discord.VoiceChannel = None
    ):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        if not ctx.user.guild_permissions.manage_guild:
            return await ctx.edit_original_response(
                content="Sorry, you are not allowed to use this command."
                "\n**Required Permission:** *Manage Server*"
            )

        if not channel and not ctx.user.voice:
            return await ctx.edit_original_response(
                content="You are neither connected to a voice channel "
                "nor specified one for me to join."
            )

        if not channel:
            channel = ctx.user.voice.channel

        if (
            not channel.permissions_for(ctx.guild.me).connect
            or not channel.permissions_for(ctx.guild.me).speak
        ):
            return await ctx.edit_original_response(
                content="Sorry, I do not have permissions to `Connect` "
                "and/or `Speak` in that voice channel."
            )

        if channel.user_limit and len(channel.members) == channel.user_limit:
            return await ctx.edit_original_response(
                content="Sorry, that voice channel is full."
            )

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player:
            pl = Player(ctx=ctx)

            try:
                _: Player = await channel.connect(cls=pl)

            except wavelink.exceptions.ChannelTimeoutException:
                return await ctx.edit_original_response(
                    content="I was unable to connect to that voice channel."
                )

        else:
            await player.move_to(channel)

        await ctx.edit_original_response(content=f"Connected to **{channel.name}**.")

    @app_commands.command(name="play", description="Play a song.")
    @app_commands.check(_initial_checks)
    @app_commands.check(_playable_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _play(self, ctx: discord.Interaction, query: str):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)

        except (
            wavelink.exceptions.LavalinkException,
            wavelink.exceptions.LavalinkLoadException,
        ):
            return await ctx.edit_original_response(
                content="An error occurred while loading associated tracks. "
                "Please try again with another query."
            )

        if not tracks:
            return await ctx.edit_original_response(
                content=f"No matches found for `{query}`!"
            )

        elif isinstance(tracks, wavelink.Playlist):
            for track in tracks:
                track.extras = {"requester_id": ctx.user.id}
                await player.queue.put_wait(track)

        else:
            track: wavelink.Playable = tracks[0]
            track.extras = {"requester_id": ctx.user.id}
            await player.queue.put_wait(track)

        if not player.playing:
            await player.do_next()

        await ctx.edit_original_response(content="Enqueued! \U0001F44C")

    @app_commands.command(
        name="search", description="Search for a song/playlist and play/queue it."
    )
    @app_commands.check(_initial_checks)
    @app_commands.check(_playable_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _search(self, ctx: discord.Interaction, query: str):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        embed = discord.Embed(color=self.bot.embed_colour)

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)

        except (
            wavelink.exceptions.LavalinkException,
            wavelink.exceptions.LavalinkLoadException,
        ):
            return await ctx.edit_original_response(
                content="An error occurred while loading associated tracks. "
                "Please try again with another query."
            )

        if not tracks:
            return await ctx.edit_original_response(
                content=f"No matches found for `{query}`!"
            )

        elif isinstance(tracks, wavelink.Playlist):
            embed.title = "Search Results - Playlist"
            embed.description = ""

            embed.add_field(
                name="Name",
                value=f"**[{tracks.name}]({tracks.url})**"
                if tracks.url
                else tracks.name,
            )

            if tracks.author:
                embed.add_field(name="Author", value=tracks.author)

            embed.add_field(name="Length", value=len(tracks.tracks))

            if tracks.artwork:
                embed.set_thumbnail(url=tracks.artwork)

            embed.description += (
                "\n\nReact with \u2705 within **a minute** to enqueue the playlist, "
                "or \U0001F6AB to cancel the search operation."
            )

            view = PlaylistConfirm()
            view.ctx = ctx
            view.playlist = tracks

            await ctx.edit_original_response(embed=embed, view=view)

        else:
            embed.title = "Search Results"
            embed.description = ""

            tracks = tracks[:4] if len(tracks) > 4 else tracks

            options = list()

            for index, track in enumerate(tracks, 1):
                embed.description += (
                    f"**{index}.** **[{track.title}]({track.uri})** by *{track.author}* "
                    f"({parse_duration(track.length)})\n\n"
                )

                options.append(discord.SelectOption(label=str(index), value=str(index)))

            embed.description += (
                "Select the song number within **a minute** to play it, "
                "or react with \U0001F6AB to cancel the search."
            )

            item = TrackSelect(options=options)
            item.ctx = ctx
            item.tracks = tracks

            view = TrackConfirm()
            view.ctx = ctx

            view.add_item(item)

            await ctx.edit_original_response(embed=embed, view=view)

    @app_commands.commands.command(
        name="pause", description="Pause the currently playing song."
    )
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _pause(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if player.paused:
            return await ctx.edit_original_response(
                content="The player is already paused."
            )

        if self.is_privileged(ctx):
            player.pause_votes.clear()
            await player.pause(True)

            return await ctx.edit_original_response(
                content="The player has been paused."
            )

        required = self.required(ctx)
        player.pause_votes.add(ctx.user)

        if len(player.pause_votes) >= required:
            player.pause_votes.clear()
            await player.pause(True)

            await ctx.edit_original_response(
                content="Vote to pause passed ... the player has been paused!"
            )

        else:
            await ctx.edit_original_response(
                content=f"{ctx.user.mention} has voted to pause the player."
            )

    @app_commands.command(
        name="resume", description="Resume the currently playing song."
    )
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _resume(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not player.paused:
            return await ctx.edit_original_response(content="The player is not paused.")

        if self.is_privileged(ctx):
            player.resume_votes.clear()
            await player.pause(False)

            return await ctx.edit_original_response(
                content="The player has been resumed."
            )

        required = self.required(ctx)
        player.resume_votes.add(ctx.user)

        if len(player.resume_votes) >= required:
            player.resume_votes.clear()
            await player.pause(False)

            return await ctx.edit_original_response(
                content="Vote to resume passed ... the player has been resumed!"
            )

        else:
            return await ctx.edit_original_response(
                content=f"{ctx.user.mention} has voted to resume the player."
            )

    @app_commands.command(
        name="seek",
        description="Seek to a specific time in the currently-playing song.",
    )
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _seek(self, ctx: discord.Interaction, position: int = 0):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not self.is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may seek the player."
            )

        if position not in range(0, int(player.current.length / 1000)):
            return await ctx.edit_original_response(
                content="The position must be between 0 and "
                "the duration of the song."
            )

        await player.seek(position * 1000)
        await ctx.edit_original_response(content=f"The player has been seeked.")

    @app_commands.command(name="skip", description="Skip the currently playing song.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _skip(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if self.is_privileged(ctx):
            player.skip_votes.clear()
            await player.skip()

            return await ctx.edit_original_response(
                content="The song has been skipped."
            )

        # noinspection PyUnresolvedReferences
        if ctx.user == self.ctx.guild.get_member(player.current.extras.requester_id):
            player.skip_votes.clear()
            await player.skip()

            return await ctx.edit_original_response(
                content="The song requester has skipped the song."
            )

        required = self.required(ctx)
        player.skip_votes.add(ctx.user)

        if len(player.skip_votes) >= required:
            player.skip_votes.clear()
            await player.skip()

            return await ctx.edit_original_response(
                content="Vote to skip passed ... the song has been skipped!"
            )

        else:
            return await ctx.edit_original_response(
                content=f"{ctx.user.mention} has voted to skip the song."
            )

    @app_commands.command(name="flush", description="Flush the queue.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _flush(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if len(player.queue) == 0:
            return await ctx.edit_original_response(
                content="No songs are queued for this server at the moment."
            )

        if self.is_privileged(ctx):
            player.queue.clear()

            return await ctx.edit_original_response(content="Queue has been flushed!")

        else:
            return await ctx.edit_original_response(
                content="You do not have permission to flush the queue."
            )

    @app_commands.command(name="stop", description="Stop the player.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _stop(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if self.is_privileged(ctx):
            await player.teardown()

            return await ctx.edit_original_response(
                content="The player has been stopped."
            )

        required = self.required(ctx)
        player.stop_votes.add(ctx.user)

        if len(player.stop_votes) >= required:
            await player.teardown()

            return await ctx.edit_original_response(
                content="Vote to stop passed ... the player has been stopped!"
            )

        else:
            return await ctx.edit_original_response(
                content=f"{ctx.user.mention} has voted to stop the player."
            )

    @app_commands.command(
        name="remove", description='Remove a song from the queue by it"s index.'
    )
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _remove(self, ctx: discord.Interaction, index: int):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if self.is_privileged(ctx):
            await player.queue.delete(index - 1)
            return await ctx.edit_original_response(
                content=f"That song has been removed!"
            )

        else:
            return await ctx.edit_original_response(
                content="Only DJ and Admins may remove songs!"
            )

    @app_commands.command(name="disconnect", description="Disconnect the player.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _disconnect(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if self.is_privileged(ctx):
            await player.teardown()

            return await ctx.edit_original_response(
                content="The player has been disconnected."
            )

        else:
            return await ctx.edit_original_response(
                content="You do not have permission to disconnect the player."
            )

    @app_commands.command(name="volume", description="Set the volume of the player.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _volume(self, ctx: discord.Interaction, volume: int = 100):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not self.is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may change the volume."
            )

        if volume not in range(0, 1001):
            return await ctx.edit_original_response(
                content="Please enter a value between 0 and 1000."
            )

        await player.set_volume(volume)
        await ctx.edit_original_response(
            content=f"The volume has been set to **{volume}%**!"
        )

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _shuffle(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if len(player.queue) < 3:
            return await ctx.edit_original_response(
                content="Add more than **3 songs** to the queue before shuffling."
            )

        if self.is_privileged(ctx):
            player.shuffle_votes.clear()
            # noinspection PyProtectedMember
            player.queue.shuffle()

            return await ctx.edit_original_response(content="Queue has been shuffled!")

        required = self.required(ctx)
        player.shuffle_votes.add(ctx.user)

        if len(player.shuffle_votes) >= required:
            player.shuffle_votes.clear()
            player.queue.shuffle()

            return await ctx.edit_original_response(
                content="Vote to shuffle passed ... the queue has been shuffled!"
            )

        else:
            return await ctx.edit_original_response(
                content=f"{ctx.user.mention} has voted to shuffle the queue."
            )

    @app_commands.command(
        name="equalizer", description="Set the equalizer of the player."
    )
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    @app_commands.choices(
        equalizer_type=[
            app_commands.Choice(name="boost", value="boost"),
            app_commands.Choice(name="flat", value="flat"),
            app_commands.Choice(name="metal", value="metal"),
            app_commands.Choice(name="piano", value="piano"),
            app_commands.Choice(name="reset", value="reset"),
        ]
    )
    async def _equalizer(
        self, ctx: discord.Interaction, equalizer_type: app_commands.Choice[str]
    ):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not self.is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may use this command."
            )

        filters: wavelink.Filters = player.filters

        if equalizer_type.value == "reset":
            filters.equalizer.reset()
            await player.set_filters(filters, seek=True)
            return await ctx.edit_original_response(
                content="The equalizer has been reset!"
            )

        bands = {
            "boost": [
                (0, -0.075),
                (1, 0.125),
                (2, 0.125),
                (3, 0.1),
                (4, 0.1),
                (5, 0.05),
                (6, 0.075),
                (7, 0.0),
                (8, 0.0),
                (9, 0.0),
                (10, 0.0),
                (11, 0.0),
                (12, 0.125),
                (13, 0.15),
                (14, 0.05),
            ],
            "flat": [
                (0, 0.0),
                (1, 0.0),
                (2, 0.0),
                (3, 0.0),
                (4, 0.0),
                (5, 0.0),
                (6, 0.0),
                (7, 0.0),
                (8, 0.0),
                (9, 0.0),
                (10, 0.0),
                (11, 0.0),
                (12, 0.0),
                (13, 0.0),
                (14, 0.0),
            ],
            "metal": [
                (0, 0.0),
                (1, 0.1),
                (2, 0.1),
                (3, 0.15),
                (4, 0.13),
                (5, 0.1),
                (6, 0.0),
                (7, 0.125),
                (8, 0.175),
                (9, 0.175),
                (10, 0.125),
                (11, 0.125),
                (12, 0.1),
                (13, 0.075),
                (14, 0.0),
            ],
            "piano": [
                (0, -0.25),
                (1, -0.25),
                (2, -0.125),
                (3, 0.0),
                (4, 0.25),
                (5, 0.25),
                (6, 0.0),
                (7, -0.25),
                (8, -0.25),
                (9, 0.0),
                (10, 0.0),
                (11, 0.5),
                (12, 0.25),
                (13, -0.025),
            ],
        }

        eq_bands = bands[equalizer_type.value]
        _dict = collections.defaultdict(float)
        _dict.update(eq_bands)
        eq_bands = [{"band": band, "gain": _dict[band]} for band in range(15)]

        filters.equalizer.set(bands=eq_bands)
        await player.set_filters(filters, seek=True)

        return await ctx.edit_original_response(
            content=f"The equalizer has been set to **{equalizer_type.name}**!"
        )

    @app_commands.command(
        name="channel_mix", description="Set the channel_mix filter for the player."
    )
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    @app_commands.choices(
        channel_mix_type=[
            app_commands.Choice(name="full_left", value="full_left"),
            app_commands.Choice(name="full_right", value="full_right"),
            app_commands.Choice(name="mono", value="mono"),
            app_commands.Choice(name="only_left", value="only_left"),
            app_commands.Choice(name="only_right", value="only_right"),
            app_commands.Choice(name="switch", value="switch"),
            app_commands.Choice(name="reset", value="reset"),
        ]
    )
    async def _channel_mix(
        self, ctx: discord.Interaction, channel_mix_type: app_commands.Choice[str]
    ):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not self.is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may use this command."
            )

        filters: wavelink.Filters = player.filters

        if channel_mix_type.value == "reset":
            filters.channel_mix.reset()
            await player.set_filters(filters, seek=True)
            return await ctx.edit_original_response(
                content="The `channel_mix` filter has been reset!"
            )

        elif channel_mix_type.value == "full_left":
            filters.channel_mix.set(
                left_to_left=1, left_to_right=0, right_to_left=1, right_to_right=0
            )

        elif channel_mix_type.value == "full_right":
            filters.channel_mix.set(
                left_to_left=0, left_to_right=1, right_to_left=0, right_to_right=1
            )

        elif channel_mix_type.value == "mono":
            filters.channel_mix.set(
                left_to_left=0.5,
                left_to_right=0.5,
                right_to_left=0.5,
                right_to_right=0.5,
            )

        elif channel_mix_type.value == "only_left":
            filters.channel_mix.set(
                left_to_left=1, left_to_right=0, right_to_left=0, right_to_right=0
            )

        elif channel_mix_type.value == "only_right":
            filters.channel_mix.set(
                left_to_left=0, left_to_right=0, right_to_left=0, right_to_right=1
            )

        elif channel_mix_type.value == "switch":
            filters.channel_mix.set(
                left_to_left=0, left_to_right=1, right_to_left=1, right_to_right=0
            )

        await player.set_filters(filters, seek=True)

        return await ctx.edit_original_response(
            content=f"The `channel_mix` filter has been set to "
            f"**{channel_mix_type.name}**!"
        )

    @app_commands.command(
        name="filter",
        description="Set the filter of the player, "
        "other than equaliser and channel_mix.",
    )
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    @app_commands.choices(
        filter_type=[
            app_commands.Choice(name="karaoke", value="karaoke"),
            app_commands.Choice(name="timescale", value="timescale"),
            app_commands.Choice(name="tremolo", value="tremolo"),
            app_commands.Choice(name="vibrato", value="vibrato"),
            app_commands.Choice(name="rotation", value="rotation"),
            app_commands.Choice(name="distortion", value="distortion"),
            app_commands.Choice(name="low_pass", value="low_pass"),
            app_commands.Choice(name="reset_all", value="reset_all"),
        ]
    )
    async def _filter(
        self, ctx: discord.Interaction, filter_type: app_commands.Choice[str]
    ):
        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.playing:
            # noinspection PyUnresolvedReferences
            return await ctx.response.send_message(
                content="I am not playing any songs in this server right now."
            )

        if not self.is_privileged(ctx):
            # noinspection PyUnresolvedReferences
            return await ctx.response.send_message(
                content="Only the DJ or admins may use this command."
            )

        modal = FilterModal()
        modal.timeout = 60

        filters: wavelink.Filters = player.filters

        if filter_type.value == "reset_all":
            filters.reset()
            await player.set_filters(filters, seek=True)
            # noinspection PyUnresolvedReferences
            return await ctx.response.send_message(
                content="All filters have been reset!"
            )

        if filter_type.value == "karaoke":
            level = ui.TextInput(
                label="Level", placeholder="1.0", required=False, default="1.0"
            )
            mono_level = ui.TextInput(
                label="Mono Level", placeholder="1.0", required=False, default="1.0"
            )
            filter_band = ui.TextInput(
                label="Filter Band",
                placeholder="220.0",
                required=False,
                default="220.0",
            )
            filter_width = ui.TextInput(
                label="Filter Width",
                placeholder="100.0",
                required=False,
                default="100.0",
            )

            modal.add_item(level)
            modal.add_item(mono_level)
            modal.add_item(filter_band)
            modal.add_item(filter_width)

            # noinspection PyUnresolvedReferences
            await ctx.response.send_modal(modal)
            res = await modal.wait()

            if res:
                return await ctx.followup.send(
                    content="Timeout! Please try again.", ephemeral=True
                )

            try:
                level = float(level.value)
                mono_level = float(mono_level.value)
                filter_band = float(filter_band.value)
                filter_width = float(filter_width.value)

            except ValueError:
                return await modal.interaction.edit_original_response(
                    content="Invalid value entered! Please try again."
                )

            filters.karaoke.set(
                level=level,
                mono_level=mono_level,
                filter_band=filter_band,
                filter_width=filter_width,
            )

        elif filter_type.value == "timescale":
            speed = ui.TextInput(
                label="Speed", placeholder="1.0", required=False, default="1.0"
            )
            pitch = ui.TextInput(
                label="Pitch", placeholder="1.0", required=False, default="1.0"
            )
            rate = ui.TextInput(
                label="Rate", placeholder="1.0", required=False, default="1.0"
            )

            modal.add_item(speed)
            modal.add_item(pitch)
            modal.add_item(rate)

            # noinspection PyUnresolvedReferences
            await ctx.response.send_modal(modal)
            res = await modal.wait()

            if res:
                return await modal.interaction.edit_original_response(
                    content="Timeout! Please try again."
                )

            try:
                speed = float(speed.value)
                pitch = float(pitch.value)
                rate = float(rate.value)

            except ValueError:
                return await modal.interaction.edit_original_response(
                    content="Invalid value entered! Please try again."
                )

            filters.timescale.set(speed=speed, pitch=pitch, rate=rate)

        elif filter_type.value == "tremolo":
            frequency = ui.TextInput(
                label="Frequency", placeholder="2.0", required=False, default="2.0"
            )
            depth = ui.TextInput(
                label="Depth", placeholder="0.5", required=False, default="0.5"
            )

            modal.add_item(frequency)
            modal.add_item(depth)

            # noinspection PyUnresolvedReferences
            await ctx.response.send_modal(modal)
            res = await modal.wait()

            if res:
                return await modal.interaction.edit_original_response(
                    content="Timeout! Please try again."
                )

            try:
                frequency = float(frequency.value)
                depth = float(depth.value)

            except ValueError:
                return await modal.interaction.edit_original_response(
                    content="Invalid value entered! Please try again."
                )

            filters.tremolo.set(frequency=frequency, depth=depth)

        elif filter_type.value == "vibrato":
            frequency = ui.TextInput(
                label="Frequency", placeholder="2.0", required=False, default="2.0"
            )
            depth = ui.TextInput(
                label="Depth", placeholder="0.5", required=False, default="0.5"
            )

            modal.add_item(frequency)
            modal.add_item(depth)

            # noinspection PyUnresolvedReferences
            await ctx.response.send_modal(modal)
            res = await modal.wait()

            if res:
                return await modal.interaction.edit_original_response(
                    content="Timeout! Please try again."
                )

            try:
                frequency = float(frequency.value)
                depth = float(depth.value)

            except ValueError:
                return await modal.interaction.edit_original_response(
                    content="Invalid value entered! Please try again."
                )

            filters.vibrato.set(frequency=frequency, depth=depth)

        elif filter_type.value == "rotation":
            frequency = ui.TextInput(
                label="Frequency", placeholder="0.2", required=False, default="0.2"
            )

            modal.add_item(frequency)

            # noinspection PyUnresolvedReferences
            await ctx.response.send_modal(modal)
            res = await modal.wait()

            if res:
                return await modal.interaction.edit_original_response(
                    content="Timeout! Please try again."
                )

            try:
                frequency = float(frequency.value)

            except ValueError:
                return await modal.interaction.edit_original_response(
                    content="Invalid value entered! Please try again."
                )

            filters.rotation.set(rotation_hz=frequency)

        elif filter_type.value == "distortion":
            offset = ui.TextInput(
                label="Offset", placeholder="0.0", required=False, default="0.0"
            )
            scale = ui.TextInput(
                label="Scale", placeholder="1.0", required=False, default="1.0"
            )
            sin_offset = ui.TextInput(
                label="Sine Offset", placeholder="0.0", required=False, default="0.0"
            )
            cos_offset = ui.TextInput(
                label="Cosine Offset", placeholder="0.0", required=False, default="0.0"
            )
            tan_offset = ui.TextInput(
                label="Tangent Offset", placeholder="0.0", required=False, default="0.0"
            )
            sin_scale = ui.TextInput(
                label="Sine scale", placeholder="1.0", required=False, default="1.0"
            )
            cos_scale = ui.TextInput(
                label="Cosine scale", placeholder="1.0", required=False, default="1.0"
            )
            tan_scale = ui.TextInput(
                label="Tangent scale", placeholder="1.0", required=False, default="1.0"
            )

            modal.add_item(offset)
            modal.add_item(scale)
            modal.add_item(sin_offset)
            modal.add_item(cos_offset)
            modal.add_item(tan_offset)
            modal.add_item(sin_scale)
            modal.add_item(cos_scale)
            modal.add_item(tan_scale)

            # noinspection PyUnresolvedReferences
            await ctx.response.send_modal(modal)
            res = await modal.wait()

            if res:
                return await modal.interaction.edit_original_response(
                    content="Timeout! Please try again."
                )

            try:
                offset = float(offset.value)
                scale = float(scale.value)
                sin_offset = float(sin_offset.value)
                cos_offset = float(cos_offset.value)
                tan_offset = float(tan_offset.value)
                sin_scale = float(sin_scale.value)
                cos_scale = float(cos_scale.value)
                tan_scale = float(tan_scale.value)

            except ValueError:
                return await modal.interaction.edit_original_response(
                    content="Invalid value entered! Please try again."
                )

            filters.distortion.set(
                offset=offset,
                scale=scale,
                sin_offset=sin_offset,
                cos_offset=cos_offset,
                tan_offset=tan_offset,
                sin_scale=sin_scale,
                cos_scale=cos_scale,
                tan_scale=tan_scale,
            )

        elif filter_type.value == "low_pass":
            smoothing = ui.TextInput(
                label="Smoothing", placeholder="20.0", required=False, default="20.0"
            )

            modal.add_item(smoothing)

            # noinspection PyUnresolvedReferences
            await ctx.response.send_modal(modal)
            res = await modal.wait()

            if res:
                return await modal.interaction.edit_original_response(
                    content="Timeout! Please try again."
                )

            try:
                smoothing = float(smoothing.value)

            except ValueError:
                return await modal.interaction.edit_original_response(
                    content="Invalid value entered! Please try again."
                )

            filters.low_pass.set(smoothing=smoothing)

        await player.set_filters(filters, seek=True)

        return await modal.interaction.edit_original_response(
            content=f"The `{filter_type.name}` filter has been set!"
        )

    @app_commands.command(name="queue", description="View the queue.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _queue(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if len(player.queue) == 0:
            return await ctx.edit_original_response(
                content="There are no more songs in the queue."
            )

        entries = list(enumerate([track for track in player.queue], 1))
        pages = QueuePaginatorSource(entries=entries, ctx=ctx)
        paginator = ViewMenuPages(
            source=pages,
            timeout=None,
            delete_message_after=False,
            clear_reactions_after=True,
        )

        await ctx.edit_original_response(content="\U0001F44C")
        await paginator.start(ctx)

    @app_commands.command(name="np", description="Show the currently playing song.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _np(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        embed, view = player.build_track_embed()

        embed.set_field_at(
            0,
            name="Position",
            value=parse_duration(player.position)
            + "/"
            + parse_duration(player.current.length),
        )

        await ctx.edit_original_response(embed=embed, view=view)

    @app_commands.command(name="loop", description="Loop the currently playing song.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _loop(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not self.is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may set the " "loop state of the player."
            )

        if not player.loop:
            player.loop = True
            return await ctx.edit_original_response(content="Looping ... \U0001F44C")

        else:
            player.loop = False
            return await ctx.edit_original_response(content="Loop removed!")

    @app_commands.command(name="loop_queue", description="Loop the queue.")
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _loop_queue(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not self.is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may set the " "loop state of the player."
            )

        if len(player.queue) == 0:
            return await ctx.edit_original_response(
                content="There are no more songs in the queue."
            )

        if not player.loop_queue:
            player.loop_queue = True
            return await ctx.edit_original_response(
                content="Looping queue ... \U0001F44C"
            )

        else:
            player.loop_queue = False
            return await ctx.edit_original_response(content="Loop removed!")

    @app_commands.command(
        name="replay",
        description="A shortcut to seek to the beginning of "
        "the currently playing song.",
    )
    @app_commands.check(_initial_checks)
    @app_commands.checks.dynamic_cooldown(dynamic_cooldown_x)
    @app_commands.guild_only()
    async def _replay(self, ctx: discord.Interaction):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not self.is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may set the " "loop state of the player."
            )

        await player.seek()

        return await ctx.edit_original_response(content="Repeating ... \U0001F44C")


async def setup(bot):
    await bot.add_cog(Music(bot))
