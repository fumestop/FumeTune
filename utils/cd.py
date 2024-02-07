from __future__ import annotations
from typing import Optional

import discord
from discord import app_commands

from utils.db import is_premium_user


async def cooldown_level_0(
    ctx: discord.Interaction,
) -> Optional[app_commands.Cooldown]:
    if ctx.client.owner == ctx.user:
        return

    elif await is_premium_user(ctx.client.pool, ctx.user.id):
        return app_commands.Cooldown(1, 2.0)

    else:
        return app_commands.Cooldown(1, 5.0)


async def cooldown_level_1(
    ctx: discord.Interaction,
) -> Optional[app_commands.Cooldown]:
    if ctx.client.owner == ctx.user:
        return

    elif await is_premium_user(ctx.client.pool, ctx.user.id):
        return app_commands.Cooldown(1, 60.0)

    else:
        return app_commands.Cooldown(1, 900.0)
