from __future__ import annotations
from typing import cast

import math

import wavelink

import discord
from discord import app_commands

from .player import Player


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


def is_privileged(ctx: discord.Interaction) -> bool:
    player: Player = cast(Player, ctx.guild.voice_client)

    return (
        player.dj == ctx.user
        or ctx.user.guild_permissions.manage_guild
        or "dj" in [role.name.lower() for role in ctx.user.roles]
    )


def required_votes(ctx: discord.Interaction) -> int:
    player: Player = cast(Player, ctx.guild.voice_client)
    channel = player.channel
    required = math.ceil((len(channel.members) - 1) / 2.5)

    if ctx.command.name == "stop":
        if len(channel.members) == 3:
            required = 2

    return required
