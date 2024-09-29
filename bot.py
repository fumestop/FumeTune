from __future__ import annotations

from typing import Any

import logging
from datetime import datetime
from itertools import cycle

import topgg
import aiohttp
import discord
import aiomysql
import wavelink
from discord.ext import tasks, commands
from discord.ext.ipc import Server
from discord.app_commands import CommandTree

import config
from utils.db import (
    add_guild,
    guild_exists,
    is_blacklisted_user,
    is_blacklisted_guild,
)


class FumeTree(CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild and await is_blacklisted_guild(
            self.client.pool, interaction.guild.id
        ):
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                "This server is currently blacklisted from using the FumeStop service. "
                "To appeal, join our community server.",
                view=discord.ui.View().add_item(
                    discord.ui.Button(
                        label="Community Server Invite",
                        url="https://fumes.top/community",
                    )
                ),
            )
            await interaction.guild.leave()
            return False

        elif await is_blacklisted_user(self.client.pool, interaction.user.id):
            # noinspection PyUnresolvedReferences
            await interaction.response.send_message(
                "You are currently blacklisted from using the FumeStop service. "
                "To appeal, join our community server:",
                view=discord.ui.View().add_item(
                    discord.ui.Button(
                        label="Community Server Invite",
                        url="https://fumes.top/community",
                    )
                ),
            )
            return False

        else:
            return True


class FumeTune(commands.AutoShardedBot):
    user: discord.ClientUser
    bot_app_info: discord.AppInfo
    session: aiohttp.ClientSession
    pool: aiomysql.Pool
    topggpy: topgg.DBLClient
    ipc: Server
    log: logging.Logger

    def __init__(self):
        description = "Unlock the ultimate music experience for YOUR Discord community with FumeTune!"

        intents = discord.Intents.default()
        intents.presences = True
        intents.members = True

        # noinspection PyTypeChecker
        super().__init__(
            command_prefix=commands.when_mentioned,
            description=description,
            heartbeat_timeout=180.0,
            intents=intents,
            help_command=None,
            tree_cls=FumeTree,
        )

        self._launch_time: datetime = Any
        self._status_items: cycle = Any

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.bot_app_info = await self.application_info()

        self.topggpy = topgg.DBLClient(bot=self, token=self.config.TOPGG_TOKEN)
        # noinspection PyTypeChecker
        self.ipc = Server(
            self,
            secret_key=self.config.IPC_SECRET_KEY,
            standard_port=self.config.IPC_STANDARD_PORT,
            multicast_port=self.config.IPC_MULTICAST_PORT,
        )

        for _extension in self.config.INITIAL_EXTENSIONS:
            try:
                await self.load_extension(_extension)
                self.log.info(f"Loaded extension {_extension}.")

            except Exception as e:
                self.log.error(f"Failed to load extension {_extension}.", exc_info=e)

    @tasks.loop(minutes=30)
    async def _update_status_items(self):
        self._status_items = cycle(
            [
                f"on {len(self.guilds)} servers | /help",
                "/invite | /vote | /community",
                "https://fumes.top/fumetune",
            ]
        )

    @tasks.loop(seconds=10)
    async def _change_status(self):
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(next(self._status_items)),
        )

    async def connect_nodes(self):
        nodes = list()

        for node in self.config.MUSIC_NODES:
            nodes.append(
                wavelink.Node(
                    identifier=node["identifier"],
                    uri=f"{'http' if node['ssl'] is False else 'https'}://{node['host']}:{node['port']}",
                    password=node["password"],
                )
            )

        await wavelink.Pool.connect(nodes=nodes, client=self, cache_capacity=100)

    async def on_ready(self) -> None:
        self._launch_time = datetime.now()

        try:
            self._update_status_items.start()
            self._change_status.start()

        except RuntimeError:
            self._update_status_items.restart()
            self._change_status.restart()

        await self.connect_nodes()

        self.log.info("FumeTune is ready.")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if message.guild and await is_blacklisted_guild(self.pool, message.guild.id):
            try:
                await message.reply(
                    content="This server is currently blacklisted from using the FumeStop service. "
                    "To appeal, join our community server.",
                    view=discord.ui.View().add_item(
                        discord.ui.Button(
                            label="Community Server Invite",
                            url="https://fumes.top/community",
                        )
                    ),
                )

            except (discord.Forbidden, discord.errors.Forbidden):
                pass

            return await message.guild.leave()

        if await is_blacklisted_user(self.pool, message.author.id):
            await message.reply(
                content="You are currently blacklisted from using the FumeStop service. "
                "To appeal, join our community server:",
                view=discord.ui.View().add_item(
                    discord.ui.Button(
                        label="Community Server Invite",
                        url="https://fumes.top/community",
                    )
                ),
            )
            return

        if message.guild and message.guild.me in message.mentions:
            await message.reply(content="Hello there! Use `/help` to get started.")

    async def on_guild_join(self, guild) -> None:
        if await is_blacklisted_guild(self.pool, guild.id):
            try:
                await guild.system_channel.send(
                    "This server has been blacklisted from using the FumeStop service. "
                    "To appeal, join our community server.",
                    view=discord.ui.View().add_item(
                        discord.ui.Button(
                            label="Community Server Invite",
                            url="https://fumes.top/community",
                        )
                    ),
                )

            except (discord.Forbidden, discord.errors.Forbidden):
                pass

            return await guild.leave()

        if not await guild_exists(self.pool, guild_id=guild.id):
            return await add_guild(self.pool, guild_id=guild.id)

    async def start(self, **kwargs) -> None:
        await super().start(config.TOKEN, reconnect=True)

    async def close(self) -> None:
        await super().close()
        await self.session.close()

        self.pool.close()
        await self.pool.wait_closed()

        self._update_status_items.stop()
        self._change_status.stop()

    @property
    def config(self):
        return __import__("config")

    @property
    def embed_color(self) -> int:
        return self.config.EMBED_COLOR

    @property
    def launch_time(self) -> datetime:
        return self._launch_time

    @property
    def owner(self) -> discord.User:
        return self.bot_app_info.owner

    @discord.utils.cached_property
    def webhook(self) -> discord.Webhook:
        return discord.Webhook.partial(
            id=self.config.WEBHOOK_ID,
            token=self.config.WEBHOOK_TOKEN,
            session=self.session,
        )
