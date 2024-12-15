from __future__ import annotations

import math
from typing import cast

import discord

from .player import Player


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
