from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

import json
import random
import string

import wavelink

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.menus.views import ViewMenuPages

from utils.cd import cooldown_level_0
from utils.tools import parse_duration
from utils.views import TrackConfirm, PlaylistConfirm
from utils.checks import initial_checks
from utils.player import Player
from utils.helpers import is_privileged, required_votes
from utils.selects import TrackSelect
from utils.paginators import QueuePaginatorSource

if TYPE_CHECKING:
    from bot import FumeTune


class Music(commands.Cog):
    def __init__(self, bot: FumeTune):
        self.bot: FumeTune = bot

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        self.bot.log.info(f"Music node {payload.node.identifier} is ready")

    @commands.Cog.listener()
    async def on_wavelink_node_disconnected(
        self, payload: wavelink.NodeDisconnectedEventPayload
    ):
        # A transient drop: wavelink reconnects to the same node on its own, so we
        # only log it here. Permanent loss surfaces via on_wavelink_node_closed.
        self.bot.log.warning(
            f"Music node {payload.node.identifier} disconnected; "
            f"wavelink will attempt to reconnect automatically."
        )

    @commands.Cog.listener()
    async def on_wavelink_node_closed(
        self, node: wavelink.Node, disconnected: list[wavelink.Player]
    ):
        # Best-effort failover: a closed node has already disconnected its players,
        # so we reconnect each one on the least-loaded healthy node and resume the
        # current track from where it left off.
        self.bot.log.warning(
            f"Music node {node.identifier} closed with "
            f"{len(disconnected)} active player(s); attempting failover."
        )

        healthy = [
            n
            for n in wavelink.Pool.nodes.values()
            if n.status is wavelink.NodeStatus.CONNECTED
            and n.identifier != node.identifier
        ]

        for player in disconnected:
            player = cast(Player, player)

            ctx = getattr(player, "ctx", None)
            channel = player.channel
            track = player.current
            position = player.position
            guild_id = getattr(player.guild, "id", "?")

            if not healthy or channel is None or ctx is None:
                self.bot.log.error(
                    f"Failover unavailable for guild {guild_id} "
                    f"(no healthy node or missing player state)."
                )
                await self._safe_send(
                    ctx,
                    "A music node went down and no backup was available. "
                    "Playback has stopped — please start again.",
                )
                continue

            target = sorted(healthy, key=lambda n: len(n.players))[0]

            try:
                new_player = Player(ctx=ctx)
                new_player.queue = player.queue
                new_player.loop = player.loop
                new_player.loop_queue = player.loop_queue
                new_player.dj = player.dj

                await channel.connect(cls=new_player, timeout=10.0)
                await new_player.set_volume(player.volume)

                if track is not None:
                    await new_player.play(
                        track, start=position, volume=player.volume
                    )

                self.bot.log.info(
                    f"Failed over guild {guild_id} to node {target.identifier}."
                )
                await self._safe_send(
                    ctx,
                    "⚠️ A music node went down — reconnected on a "
                    "backup node and resumed playback.",
                )

            except Exception as exc:
                self.bot.log.error(f"Failover failed for guild {guild_id}: {exc!r}")
                await self._safe_send(
                    ctx,
                    "A music node went down and reconnecting to a backup failed. "
                    "Playback has stopped — please start again.",
                )

    @staticmethod
    async def _safe_send(ctx: discord.Interaction | None, message: str):
        if ctx is None:
            return

        try:
            await ctx.channel.send(content=message)

        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_wavelink_track_exception(
        self, payload: wavelink.TrackExceptionEventPayload
    ):
        player: Player | None = payload.player

        if not player:
            return

        player.loop = False
        player.loop_queue = False

        await player.do_next()

        await player.ctx.channel.send(
            content="The song encountered an error, **it is being skipped** "
            "(Any loops if set have been removed)."
        )

        embed = discord.Embed(colour=self.bot.embed_color)
        embed.add_field(name="Track", value=f"`{payload.track.title}`", inline=False)

        # noinspection PyUnresolvedReferences
        exception = {
            "title": payload.track.title,
            "source": payload.track.source,
            "severity": payload.exception["severity"],
            "cause": payload.exception["cause"],
            "message": payload.exception["message"],
        }

        file_name = (
            f"logs/tracks/{payload.track.identifier}-"
            f"{''.join(random.choices(string.ascii_letters + string.digits, k=10))}.log"
        )

        with open(file_name, "w") as f:
            json.dump(exception, f, indent=4)

        embed.add_field(name="Log", value=f"Saved to `{file_name}`", inline=False)

        await self.bot.webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(
        self, payload: wavelink.TrackStuckEventPayload
    ):
        player: Player = cast(Player, payload.player)

        if not player:
            return

        player.queue.put_at(0, payload.track)
        await player.do_next()

        await player.ctx.channel.send(
            content="The song got stuck, **it is being replayed.**"
        )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: Player = cast(Player, payload.player)

        if not player:
            return

        if player.loop:
            player.queue.put_at(0, payload.original)

        elif player.loop_queue:
            await player.queue.put_wait(payload.original)

        if player.queue.count == 0:
            await player.ctx.channel.send(
                content="End of queue reached, add more songs to continue playing. "
                "The player will automatically disconnect in **5 minutes** if no songs are added."
            )

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
            return await player.teardown()

        channel = player.channel

        if len(channel.members) == 1:
            return await player.teardown()

        if member == player.dj and after.channel is None:
            for m in channel.members:
                if m.bot:
                    continue

                else:
                    player.dj = m
                    return

        elif after.channel == channel and player.dj not in channel.members:
            player.dj = member

    async def _ensure_voice(self, ctx: discord.Interaction) -> bool:
        """Connect to the invoker's voice channel unless already connected.

        Returns ``True`` when the bot is connected and ready, or ``False`` after
        sending an error response (missing permissions, full channel, or a
        connection timeout).
        """
        channel = ctx.user.voice.channel

        if ctx.guild.me.voice and ctx.guild.me.voice.channel == channel:
            return True

        if (
            not channel.permissions_for(ctx.guild.me).connect
            or not channel.permissions_for(ctx.guild.me).speak
        ):
            await ctx.edit_original_response(
                content="Sorry, I do not have permissions to `Connect` and/or `Speak` in that voice channel."
            )
            return False

        if channel.user_limit and len(channel.members) == channel.user_limit:
            await ctx.edit_original_response(
                content="Sorry, that voice channel is full."
            )
            return False

        if not ctx.channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.edit_original_response(
                content="Sorry, I do not have permissions to send messages in this channel."
            )
            return False

        try:
            await channel.connect(cls=Player(ctx=ctx), timeout=10.0)

        except wavelink.exceptions.ChannelTimeoutException:
            await ctx.edit_original_response(
                content="I was unable to connect to that voice channel."
            )
            return False

        return True

    @app_commands.command(name="play")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _play(self, ctx: discord.Interaction, query: str):
        """Play a song from YouTube or Spotify.

        Parameters
        ----------
        query: str
            The song/playlist to play. Can be a YouTube URL, Spotify URL, or a search query.

        """
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        if not await self._ensure_voice(ctx):
            return

        player: Player = cast(Player, ctx.guild.voice_client)

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)

        except (
            wavelink.exceptions.LavalinkException,
            wavelink.exceptions.LavalinkLoadException,
            wavelink.exceptions.NodeException,
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
            if any(track.length > 24 * 60 * 60 * 1000 for track in tracks.tracks):
                return await ctx.edit_original_response(
                    content="Sorry, one or more songs are too long to be played **(>24 hours)**."
                )

            for track in tracks.tracks:
                track.extras = {"requester_id": ctx.user.id}
                await player.queue.put_wait(track)

        else:
            track: wavelink.Playable = tracks[0]

            if track.length > 24 * 60 * 60 * 1000:
                return await ctx.edit_original_response(
                    content="Sorry, the song is too long to be played **(>24 hours)**."
                )

            track.extras = {"requester_id": ctx.user.id}
            await player.queue.put_wait(track)

        if not player.playing:
            await player.do_next()

        await ctx.edit_original_response(content="Enqueued! \U0001f44c")

    @app_commands.command(name="search")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _search(self, ctx: discord.Interaction, query: str):
        """Search for a song/playlist and play/queue it.

        Parameters
        ----------
        query: str
            The song/playlist to search for. Can be a YouTube URL, Spotify URL, or a search query.

        """
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        if not await self._ensure_voice(ctx):
            return

        embed = discord.Embed(color=self.bot.embed_color)

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)

        except (
            wavelink.exceptions.LavalinkException,
            wavelink.exceptions.LavalinkLoadException,
            wavelink.exceptions.NodeException,
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
                value=(
                    f"**[{tracks.name}]({tracks.url})**"
                    if tracks.url
                    else tracks.name
                ),
            )

            if tracks.author:
                embed.add_field(name="Author", value=tracks.author)

            embed.add_field(name="Length", value=len(tracks.tracks))

            if tracks.artwork:
                embed.set_thumbnail(url=tracks.artwork)

            embed.description += (
                "\n\nReact with \u2705 within **a minute** to enqueue the playlist, "
                "or \U0001f6ab to cancel the search operation."
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

                options.append(
                    discord.SelectOption(label=str(index), value=str(index))
                )

            embed.description += (
                "Select the song number within **a minute** to play it, "
                "or react with \U0001f6ab to cancel the search."
            )

            item = TrackSelect(options=options)
            item.ctx = ctx
            item.tracks = tracks

            view = TrackConfirm()
            view.ctx = ctx

            view.add_item(item)

            await ctx.edit_original_response(embed=embed, view=view)

    @app_commands.command(name="summon")
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _summon(
        self,
        ctx: discord.Interaction,
        channel: Optional[discord.VoiceChannel] = None,
    ):
        """Summon the bot to a voice channel.

        Parameters
        ----------
        channel: discord.VoiceChannel
            The voice channel to join.

        """
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
                _: Player = await channel.connect(cls=pl, timeout=10.0)

            except wavelink.exceptions.ChannelTimeoutException:
                return await ctx.edit_original_response(
                    content="I was unable to connect to that voice channel."
                )

        else:
            await player.move_to(channel)

        await ctx.edit_original_response(content=f"Connected to {channel.mention}.")

    @app_commands.commands.command(name="pause")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _pause(self, ctx: discord.Interaction):
        """Pause the currently playing song."""
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

        if is_privileged(ctx):
            player.pause_votes.clear()
            await player.pause(True)

            return await ctx.edit_original_response(
                content="The player has been paused."
            )

        required = required_votes(ctx)
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

    @app_commands.command(name="resume")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _resume(self, ctx: discord.Interaction):
        """Resume the currently playing song."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not player.paused:
            return await ctx.edit_original_response(
                content="The player is not paused."
            )

        if is_privileged(ctx):
            player.resume_votes.clear()
            await player.pause(False)

            return await ctx.edit_original_response(
                content="The player has been resumed."
            )

        required = required_votes(ctx)
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

    @app_commands.command(name="skip")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _skip(self, ctx: discord.Interaction):
        """Skip the currently playing song."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if is_privileged(ctx):
            player.skip_votes.clear()
            await player.skip()

            return await ctx.edit_original_response(
                content="The song has been skipped."
            )

        if ctx.user.id == player.current.extras.requester_id:
            player.skip_votes.clear()
            await player.skip()

            return await ctx.edit_original_response(
                content="The song requester has skipped the song."
            )

        required = required_votes(ctx)
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

    @app_commands.command(name="seek")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _seek(self, ctx: discord.Interaction, position: Optional[int] = 0):
        """Seek to a specific time in the currently-playing song.

        Parameters
        ----------
        position: int
            The position to seek to (in seconds).

        """
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not is_privileged(ctx):
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

    @app_commands.command(name="replay")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _replay(self, ctx: discord.Interaction):
        """Replay the currently playing song, from start."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may set the loop state of the player."
            )

        await player.seek()

        return await ctx.edit_original_response(content="Repeating ... \U0001f44c")

    @app_commands.command(name="volume")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _volume(self, ctx: discord.Interaction, volume: Optional[int] = 100):
        """Set the volume of the player.

        Parameters
        ----------
        volume: Optional[int]
            The volume to set (0-1000). Leave empty to reset to 100.

        """
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not is_privileged(ctx):
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

    @app_commands.command(name="now")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _now(self, ctx: discord.Interaction):
        """Show the currently playing song."""
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
            value=f"`{parse_duration(player.position)}/{parse_duration(player.current.length)}`",
        )

        await ctx.edit_original_response(embed=embed, view=view)

    @app_commands.command(name="queue")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _queue(self, ctx: discord.Interaction):
        """View the player queue."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if player.queue.count == 0:
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

        await ctx.edit_original_response(content="\U0001f44c")
        await paginator.start(ctx)

    @app_commands.command(name="remove")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _remove(self, ctx: discord.Interaction, position: int):
        """Remove a song from the queue by its index.

        Parameters
        ----------
        position: int
            The position of the song to remove.

        """
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may remove songs!"
            )

        if position not in range(1, len(player.queue) + 1):
            return await ctx.edit_original_response(
                content="Please enter a valid position in the queue."
            )

        player.queue.delete(position - 1)

        return await ctx.edit_original_response(
            content=f"That song has been removed!"
        )

    @app_commands.command(name="flush")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _flush(self, ctx: discord.Interaction):
        """Flush the queue."""
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

        if is_privileged(ctx):
            player.queue.clear()

            return await ctx.edit_original_response(
                content="Queue has been flushed!"
            )

        else:
            return await ctx.edit_original_response(
                content="You do not have permission to flush the queue."
            )

    @app_commands.command(name="shuffle")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _shuffle(self, ctx: discord.Interaction):
        """Shuffle the queue."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if player.queue.count < 3:
            return await ctx.edit_original_response(
                content="Add more than **3 songs** to the queue before shuffling."
            )

        if is_privileged(ctx):
            player.shuffle_votes.clear()
            player.queue.shuffle()

            return await ctx.edit_original_response(
                content="Queue has been shuffled!"
            )

        required = required_votes(ctx)
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

    @app_commands.command(name="loop")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _loop(self, ctx: discord.Interaction):
        """Loop the currently playing song."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may set the loop state of the player."
            )

        if not player.loop:
            player.loop = True
            return await ctx.edit_original_response(content="Looping ... \U0001f44c")

        else:
            player.loop = False
            return await ctx.edit_original_response(content="Loop removed!")

    @app_commands.command(name="loop_queue")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _loop_queue(self, ctx: discord.Interaction):
        """Loop the entire queue."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may set the loop state of the player."
            )

        if len(player.queue) == 0:
            return await ctx.edit_original_response(
                content="There are no more songs in the queue."
            )

        if not player.loop_queue:
            player.loop_queue = True
            return await ctx.edit_original_response(
                content="Looping queue ... \U0001f44c"
            )

        else:
            player.loop_queue = False
            return await ctx.edit_original_response(content="Loop removed!")

    @app_commands.command(name="stop")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _stop(self, ctx: discord.Interaction):
        """Stop the player."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if is_privileged(ctx):
            await player.teardown()

            return await ctx.edit_original_response(
                content="The player has been stopped."
            )

        required = required_votes(ctx)
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

    @app_commands.command(name="disconnect")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.guild_only()
    async def _disconnect(self, ctx: discord.Interaction):
        """Disconnect the player."""
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.connected:
            return await ctx.edit_original_response(
                content="I am not playing any songs in this server right now."
            )

        if not is_privileged(ctx):
            return await ctx.edit_original_response(
                content="Only the DJ or admins may disconnect the player."
            )

        await player.teardown()

        return await ctx.edit_original_response(
            content="The player has been disconnected."
        )


async def setup(bot):
    await bot.add_cog(Music(bot))
