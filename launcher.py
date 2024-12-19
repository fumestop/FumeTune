from __future__ import annotations

import sys
import asyncio
import logging
import contextlib
from datetime import datetime

import click
import discord
import pymysql
import aiomysql

from bot import FumeTune

import config

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

else:
    # noinspection PyUnresolvedReferences
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def create_pool() -> aiomysql.Pool:
    return await aiomysql.create_pool(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        db=config.DB_NAME,
        autocommit=True,
        loop=asyncio.get_event_loop(),
    )


class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name="discord.state")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelname == "WARNING" and "referencing an unknown" in record.msg:
            return False
        return True


@contextlib.contextmanager
def setup_logging():
    log = logging.getLogger()

    try:
        handler = logging.FileHandler(
            filename=f"logs/fumetune-{datetime.now().strftime('%Y-%m-%d~%H-%M-%S')}.log",
            encoding="utf-8",
            mode="w",
        )

        discord.utils.setup_logging(handler=handler)

        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
        logging.getLogger("discord.state").addFilter(RemoveNoise())

        log.setLevel(logging.INFO)

        yield

    finally:
        handlers = log.handlers[:]
        for _handler in handlers:
            _handler.close()
            log.removeHandler(_handler)


async def run_bot():
    log = logging.getLogger()

    try:
        pool = await create_pool()

    except pymysql.err.OperationalError:
        click.echo("Could not set up MySQL. Exiting.", file=sys.stderr)
        return log.exception("Could not set up MySQL. Exiting...")

    async with FumeTune() as bot:
        bot.log = log
        bot.pool = pool
        await bot.start()


@click.group(invoke_without_command=True, options_metavar="[options]")
@click.pass_context
def main(ctx):
    if ctx.invoked_subcommand is None:
        with setup_logging():
            asyncio.run(run_bot())


if __name__ == "__main__":
    main()
