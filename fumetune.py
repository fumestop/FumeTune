import json
import logging
import asyncio
from datetime import datetime

import discord
from discord.ext import commands

from utils.cogs import load_cogs

with open("config.json") as json_file:
    data = json.load(json_file)

    token = data["bot_token"]
    embed_color = data["embed_color"]

logging.basicConfig(
    level=logging.INFO,
    filename=f"logs/fumeguard-{datetime.now().strftime('%Y-%m-%d~%H-%M-%S')}.log",
    filemode="w",
    format="%(asctime)s - [%(levelname)s] %(message)s",
)


class FumeTune(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger()
        self.launch_time = datetime.utcnow()

        self.embed_colour = int(hex(embed_color), 16)


intents = discord.Intents.default()
intents.members = True

bot = FumeTune(
    command_prefix=commands.when_mentioned_or("/"), intents=intents, help_command=None
)


async def main():
    async with bot:
        await load_cogs(bot)
        await bot.start(token)


asyncio.run(main())
