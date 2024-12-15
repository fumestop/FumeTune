from __future__ import annotations

import aiomysql


async def guild_exists(pool: aiomysql.Pool, guild_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "select GUILD_ID from guilds where GUILD_ID = %s;", (guild_id,)
            )

            res = await cur.fetchone()

    if not res:
        return False

    return True


async def add_guild(pool: aiomysql.Pool, guild_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("insert into guilds (GUILD_ID) values (%s);", (guild_id,))


async def is_premium_user(pool: aiomysql.Pool, user_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "select PREMIUM from users where USER_ID = %s;", (user_id,)
            )

            res = await cur.fetchone()

    if not res or not res[0]:
        return False

    return True


async def is_premium_guild(pool: aiomysql.Pool, user_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "select PREMIUM from guilds where GUILD_ID = %s;", (user_id,)
            )

            res = await cur.fetchone()

    if not res or not res[0]:
        return False

    return True


async def is_blacklisted_user(pool: aiomysql.Pool, user_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "select USER_ID from user_blacklist where USER_ID = %s;", (user_id,)
            )

            res = await cur.fetchone()

    if not res or not res[0]:
        return False

    return True


async def is_blacklisted_guild(pool: aiomysql.Pool, guild_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "select GUILD_ID from guild_blacklist where GUILD_ID = %s;",
                (guild_id,),
            )

            res = await cur.fetchone()

    if not res or not res[0]:
        return False

    return True
