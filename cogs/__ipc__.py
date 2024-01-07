import json

from discord.ext import commands
from discord.ext.ipc import Server
from discord.ext.ipc.objects import ClientPayload


class IPC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        with open("config.json") as json_file:
            data = json.load(json_file)
            self.secret_key = data["secret_key"]
            self.standard_port = data["standard_port"]
            self.multicast_port = data["multicast_port"]

        if not hasattr(bot, "ipc"):
            bot.ipc = Server(
                self.bot,
                secret_key=self.secret_key,
                standard_port=self.standard_port,
                multicast_port=self.multicast_port,
            )

    async def cog_load(self):
        await self.bot.ipc.start()

    async def cog_unload(self):
        await self.bot.ipc.stop()

    # noinspection PyUnusedLocal
    @Server.route(name="get_guild_count")
    async def _get_guild_count(self, data: ClientPayload):
        return {"count": len(self.bot.guilds)}

    # noinspection PyUnusedLocal
    @Server.route(name="get_user_count")
    async def _get_user_count(self, data: ClientPayload):
        return {"count": len(self.bot.users)}

    # noinspection PyUnusedLocal
    @Server.route(name="get_command_count")
    async def _get_command_count(self, data: ClientPayload):
        _commands = await self.bot.tree.fetch_commands()
        return {"count": len(_commands)}


async def setup(bot):
    await bot.add_cog(IPC(bot))
