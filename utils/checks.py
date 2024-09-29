from __future__ import annotations

from typing import cast

import discord
from discord import app_commands

from .player import Player
from .helpers import is_privileged


def initial_checks(ctx: discord.Interaction) -> bool:
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

    if is_privileged(ctx):
        return True

    if player.connected:
        if ctx.user not in player.channel.members:
            raise app_commands.CheckFailure(
                f"You must be connected to `{player.channel.name}`."
            )

    return True
