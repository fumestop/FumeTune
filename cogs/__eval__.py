import io
import json
import inspect
import asyncio
import textwrap
import traceback
import subprocess
from contextlib import redirect_stdout

import discord
from discord import app_commands
from discord.ext import commands


with open("config.json") as json_file:
    data = json.load(json_file)
    community_server_id = data["community_server_id"]


class Evaluate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # noinspection PyBroadException
    @app_commands.command(name="eval")
    @app_commands.guilds(community_server_id)
    async def _eval(self, ctx: discord.Interaction, *, body: str):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        if not await self.bot.is_owner(ctx.user):
            await ctx.edit_original_response(
                content="Sorry, this is an owner(s) only command!"
            )

        env = {
            "discord": discord,
            "ctx": ctx,
            "bot": self.bot,
            "channel": ctx.channel,
            "user": ctx.user,
            "guild": ctx.guild,
            "message": ctx.message,
            "source": inspect.getsource,
            "asyncio": asyncio,
        }

        def cleanup_code(content):
            if content.startswith("```") and content.endswith("```"):
                return "\n".join(content.split("\n")[1:-1])

            return content.strip("` \n")

        env.update(globals())

        body = cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        def paginate(text: str):
            app_index = 0
            last = 0
            curr = 0
            pages = []

            for curr in range(0, len(text)):
                if curr % 1980 == 0:
                    pages.append(text[last:curr])
                    last = curr
                    app_index = curr

            if app_index != len(text) - 1:
                pages.append(text[last:curr])

            return list(filter(lambda a: a != "", pages))

        try:
            exec(to_compile, env)

        except Exception as e:
            await ctx.edit_original_response(
                content=f"```py\n{e.__class__.__name__}: {e}\n```"
            )

        func = env["func"]

        try:
            with redirect_stdout(stdout):
                # noinspection PyUnresolvedReferences,PyArgumentList
                ret = await func()

        except:
            value = stdout.getvalue()
            await ctx.edit_original_response(
                content=f"```py\n{value}{traceback.format_exc()}\n```"
            )

        else:
            value = stdout.getvalue()
            if ret is None:
                if value:
                    try:
                        await ctx.edit_original_response(content=f"```py\n{value}\n```")
                    except:
                        paginated_text = paginate(value)
                        for page in paginated_text:
                            if page == paginated_text[-1]:
                                await ctx.edit_original_response(
                                    content=f"```py\n{page}\n```"
                                )
                                break
                            await ctx.edit_original_response(
                                content=f"```py\n{page}\n```"
                            )
            else:
                try:
                    await ctx.edit_original_response(
                        content=f"```py\n{value}{ret}\n```"
                    )
                except:
                    paginated_text = paginate(f"{value}{ret}")
                    for page in paginated_text:
                        if page == paginated_text[-1]:
                            await ctx.edit_original_response(
                                content=f"```py\n{page}\n```"
                            )
                            break
                        await ctx.edit_original_response(content=f"```py\n{page}\n```")

    @app_commands.command(name="exec")
    @app_commands.guilds(community_server_id)
    async def _exec(self, ctx: discord.Interaction, *, command: str):
        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        if not await self.bot.is_owner(ctx.user):
            await ctx.edit_original_response(
                content="Sorry, this is an owner(s) only command!"
            )

        proc = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        stdout_value = proc.stdout.decode("utf-8") + proc.stderr.decode("utf-8")

        stdout_value = "\n".join(stdout_value.split("\n")[-10:])

        await ctx.edit_original_response(content="```sh\n" + stdout_value + "```")


async def setup(bot):
    await bot.add_cog(Evaluate(bot))
