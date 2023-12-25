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

logging.basicConfig(
    level=logging.DEBUG,
    filename="logs/fumetune.log",
    filemode="w",
    format="%(asctime)s - [%(levelname)s] %(message)s",
)


class FumeTune(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger("FumeTune")


intents = discord.Intents.default()
bot = FumeTune(command_prefix=commands.when_mentioned_or("/"), intents=intents)

bot.launch_time = datetime.utcnow()
bot.remove_command("help")


bot.embed_colour = 0xE44C65


async def main():
    async with bot:
        await load_cogs(bot)
        await bot.start(token)


asyncio.run(main())
