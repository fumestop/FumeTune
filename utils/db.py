import json
import asyncio

import aiomysql

with open("config.json") as json_file:
    data = json.load(json_file)
    db_name = data["db_name"]
    db_user = data["db_user"]
    db_password = data["db_password"]
    db_host = data["db_host"]
    db_port = data["db_port"]


async def guild_exists(guild_id: int):
    pool = await aiomysql.create_pool(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        db=db_name,
        autocommit=True,
        loop=asyncio.get_event_loop(),
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"select GUILD_ID from guilds where GUILD_ID = %s;", (guild_id,)
            )

            res = await cur.fetchone()

    pool.close()
    await pool.wait_closed()

    if not res:
        return False

    return True


async def add_guild(guild_id: int):
    pool = await aiomysql.create_pool(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        db=db_name,
        autocommit=True,
        loop=asyncio.get_event_loop(),
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("insert into guilds (GUILD_ID) values (%s);", (guild_id,))

    pool.close()
    await pool.wait_closed()


async def is_premium_user(user_id: int):
    pool = await aiomysql.create_pool(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        db=db_name,
        autocommit=True,
        loop=asyncio.get_event_loop(),
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "select PREMIUM from users where USER_ID = %s;", (user_id,)
            )

            res = await cur.fetchone()

    pool.close()
    await pool.wait_closed()

    if not res or not res[0]:
        return False

    return True


async def is_premium_guild(user_id: int):
    pool = await aiomysql.create_pool(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        db=db_name,
        autocommit=True,
        loop=asyncio.get_event_loop(),
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "select PREMIUM from guilds where GUILD_ID = %s;", (user_id,)
            )

            res = await cur.fetchone()

    pool.close()
    await pool.wait_closed()

    if not res or not res[0]:
        return False

    return True
