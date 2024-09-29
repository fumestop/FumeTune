from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands
from discord.ext.ipc import Server
from discord.ext.ipc.objects import ClientPayload

if TYPE_CHECKING:
    from bot import FumeTune


class IPC(commands.Cog):
    def __init__(self, bot: FumeTune):
        self.bot: FumeTune = bot

    async def cog_load(self):
        await self.bot.ipc.start()

    async def cog_unload(self):
        await self.bot.ipc.stop()

    # noinspection PyUnusedLocal
    @Server.route(name="get_guild_count")
    async def _get_guild_count(self, data: ClientPayload):
        return {"status": 200, "count": len(self.bot.guilds)}

    # noinspection PyUnusedLocal
    @Server.route(name="get_user_count")
    async def _get_user_count(self, data: ClientPayload):
        return {"status": 200, "count": len(self.bot.users)}

    # noinspection PyUnusedLocal
    @Server.route(name="get_command_count")
    async def _get_command_count(self, data: ClientPayload):
        _commands = await self.bot.tree.fetch_commands()
        return {"status": 200, "count": len(_commands)}

    @Server.route(name="get_channel_list")
    async def _get_channel_list(self, data: ClientPayload):
        guild = self.bot.get_guild(data.guild_id)

        if not guild:
            return {"error": {"code": 404, "message": "Guild not found."}}

        channels = dict()

        for channel in guild.text_channels:
            if not channel.permissions_for(guild.me).send_messages:
                continue

            else:
                channels[channel.id] = channel.name

        return {"channels": channels}

    @Server.route(name="get_mutual_guilds")
    async def _get_mutual_guilds(self, data: ClientPayload):
        user = self.bot.get_user(data.user_id)

        if not user:
            return {"error": {"code": 404, "message": "User not found."}}

        guilds = dict()

        for guild in user.mutual_guilds:
            member = await guild.fetch_member(user.id)

            guilds[guild.id] = {
                "name": guild.name,
                "member_manage_guild": member.guild_permissions.manage_guild,
                "bot_manage_nicknames": guild.me.guild_permissions.manage_nicknames,
            }

        return {"guilds": guilds}


async def setup(bot: FumeTune):
    await bot.add_cog(IPC(bot))
