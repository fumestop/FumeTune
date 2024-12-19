from __future__ import annotations

from typing import TYPE_CHECKING, cast

import collections

import wavelink

import discord
from discord import ui, app_commands
from discord.ext import commands

from utils.cd import cooldown_level_0
from utils.checks import initial_checks
from utils.modals import FilterModal
from utils.player import Player
from utils.helpers import is_privileged

if TYPE_CHECKING:
    from bot import FumeTune


@app_commands.guild_only()
class Filters(
    commands.GroupCog,
    group_name="filter",
    group_description="Various commands to manage audio filters.",
):
    def __init__(self, bot: FumeTune):
        self.bot: FumeTune = bot

    @app_commands.command(name="equalizer")
    @app_commands.rename(equalizer_type="type")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.choices(
        equalizer_type=[
            app_commands.Choice(name="Boost", value="boost"),
            app_commands.Choice(name="Flat", value="flat"),
            app_commands.Choice(name="Metal", value="metal"),
            app_commands.Choice(name="Piano", value="piano"),
            app_commands.Choice(name="Reset", value="reset"),
        ]
    )
    async def _filter_equalizer(
        self, ctx: discord.Interaction, equalizer_type: app_commands.Choice[str]
    ):
        """Set the equalizer of the player.

        Parameters
        ----------
        equalizer_type : app_commands.Choice[str]
            The type of equalizer to set.

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

    @app_commands.command(name="channel_mix")
    @app_commands.rename(channel_mix_type="type")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.choices(
        channel_mix_type=[
            app_commands.Choice(name="Full Left", value="full_left"),
            app_commands.Choice(name="Full Right", value="full_right"),
            app_commands.Choice(name="Mono", value="mono"),
            app_commands.Choice(name="Only Left", value="only_left"),
            app_commands.Choice(name="Only Right", value="only_right"),
            app_commands.Choice(name="Switch", value="switch"),
            app_commands.Choice(name="Reset", value="reset"),
        ]
    )
    async def _filter_channel_mix(
        self, ctx: discord.Interaction, channel_mix_type: app_commands.Choice[str]
    ):
        """Set the channel mix filter for the player.

        Parameters
        ----------
        channel_mix_type : app_commands.Choice[str]
            The type of channel mix filter to set.

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
                content="Only the DJ or admins may use this command."
            )

        filters: wavelink.Filters = player.filters

        if channel_mix_type.value == "reset":
            filters.channel_mix.reset()
            await player.set_filters(filters, seek=True)
            return await ctx.edit_original_response(
                content="The `channel mix` filter has been reset!"
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
            content=f"The `channel mix` filter has been set to "
            f"**{channel_mix_type.name}**!"
        )

    @app_commands.command(name="other")
    @app_commands.rename(filter_type="type")
    @app_commands.check(initial_checks)
    @app_commands.checks.dynamic_cooldown(cooldown_level_0)
    @app_commands.choices(
        filter_type=[
            app_commands.Choice(name="Karaoke", value="karaoke"),
            app_commands.Choice(name="Timescale", value="timescale"),
            app_commands.Choice(name="Tremolo", value="tremolo"),
            app_commands.Choice(name="Vibrato", value="vibrato"),
            app_commands.Choice(name="Rotation", value="rotation"),
            app_commands.Choice(name="Distortion", value="distortion"),
            app_commands.Choice(name="Low Pass", value="low_pass"),
            app_commands.Choice(name="Reset All", value="reset_all"),
        ]
    )
    async def _filter_other(
        self, ctx: discord.Interaction, filter_type: app_commands.Choice[str]
    ):
        """Set the filter of the player, other than equalizer and channel_mix.

        Parameters
        ----------
        filter_type : app_commands.Choice[str]
            The type of filter to set.

        """
        player: Player = cast(Player, ctx.guild.voice_client)

        if not player or not player.playing:
            # noinspection PyUnresolvedReferences
            return await ctx.response.send_message(
                content="I am not playing any songs in this server right now."
            )

        if not is_privileged(ctx):
            # noinspection PyUnresolvedReferences
            return await ctx.response.send_message(
                content="Only the DJ or admins may use this command."
            )

        modal = FilterModal()
        modal.ctx = ctx

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
                label="Cosine Offset",
                placeholder="0.0",
                required=False,
                default="0.0",
            )
            tan_offset = ui.TextInput(
                label="Tangent Offset",
                placeholder="0.0",
                required=False,
                default="0.0",
            )
            sin_scale = ui.TextInput(
                label="Sine scale", placeholder="1.0", required=False, default="1.0"
            )
            cos_scale = ui.TextInput(
                label="Cosine scale",
                placeholder="1.0",
                required=False,
                default="1.0",
            )
            tan_scale = ui.TextInput(
                label="Tangent scale",
                placeholder="1.0",
                required=False,
                default="1.0",
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


async def setup(bot: FumeTune):
    await bot.add_cog(Filters(bot))
