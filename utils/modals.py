from __future__ import annotations

from typing import Optional

import discord
from discord import ui


class EvalModal(ui.Modal, title="Evaluate Code"):
    ctx: Optional[discord.Interaction] = None
    interaction: Optional[discord.Interaction] = None

    timeout: int = 5 * 60

    code = ui.TextInput(
        label="Code",
        placeholder="Enter the code to evaluate",
        style=discord.TextStyle.paragraph,
        required=True,
    )

    async def on_submit(self, ctx: discord.Interaction):
        self.interaction = ctx

        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

    async def on_timeout(self):
        await self.ctx.followup.send(
            content="Timeout! Please try again.", ephemeral=True
        )


class ExecModal(ui.Modal, title="Execute Shell Commands"):
    ctx: Optional[discord.Interaction] = None
    interaction: Optional[discord.Interaction] = None

    timeout: int = 5 * 60

    sh_commands = ui.TextInput(
        label="Command(s)",
        placeholder="Enter the command(s) to execute",
        style=discord.TextStyle.paragraph,
        required=True,
    )

    async def on_submit(self, ctx: discord.Interaction):
        self.interaction = ctx

        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

    async def on_timeout(self):
        await self.ctx.followup.send(
            content="Timeout! Please try again.", ephemeral=True
        )


class FilterModal(ui.Modal, title="Filter Parameters"):
    ctx: Optional[discord.Interaction] = None
    interaction: Optional[discord.Interaction] = None

    timeout: int = 5 * 60

    async def on_submit(self, ctx: discord.Interaction) -> None:
        self.interaction = ctx

        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

    async def on_timeout(self) -> None:
        await self.ctx.followup.send(
            content="Timeout! Please try again.", ephemeral=True
        )
