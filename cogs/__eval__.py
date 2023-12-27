import io
import json
import inspect
import asyncio
import textwrap
import traceback
import subprocess
from contextlib import redirect_stdout

import discord
from discord import ui, app_commands
from discord.ext import commands


with open("config.json") as json_file:
    data = json.load(json_file)
    community_server_id = data["community_server_id"]


class EvalModal(ui.Modal, title="Evaluate Code"):
    code = ui.TextInput(
        label="Code",
        placeholder="The code to evaluate...",
        style=discord.TextStyle.paragraph,
    )

    bot: commands.AutoShardedBot = None
    interaction: discord.Interaction = None

    # noinspection PyBroadException
    async def on_submit(self, ctx: discord.Interaction):
        self.interaction = ctx

        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        env = {
            "discord": discord,
            "ctx": ctx,
            "bot": self.bot,
            "self.bot": self.bot,
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

        body = cleanup_code(self.code.value)
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
            await self.interaction.edit_original_response(
                content=f"```py\n{e.__class__.__name__}: {e}\n```"
            )

        func = env["func"]

        try:
            with redirect_stdout(stdout):
                # noinspection PyUnresolvedReferences,PyArgumentList
                ret = await func()

        except Exception as _:
            value = stdout.getvalue()
            await self.interaction.edit_original_response(
                content=f"```py\n{value}{traceback.format_exc()}\n```"
            )

        else:
            value = stdout.getvalue()

            if ret is None:
                if value:
                    try:
                        await self.interaction.edit_original_response(
                            content=f"```py\n{value}\n```"
                        )

                    except Exception as _:
                        paginated_text = paginate(value)

                        for page in paginated_text:
                            if page == paginated_text[-1]:
                                await self.interaction.edit_original_response(
                                    content=f"```py\n{page}\n```"
                                )
                                break
                            await self.interaction.edit_original_response(
                                content=f"```py\n{page}\n```"
                            )
                else:
                    await self.interaction.edit_original_response(content="\U00002705")

            else:
                try:
                    await self.interaction.edit_original_response(
                        content=f"```py\n{value}{ret}\n```"
                    )

                except Exception as _:
                    paginated_text = paginate(f"{value}{ret}")

                    for page in paginated_text:
                        if page == paginated_text[-1]:
                            await self.interaction.edit_original_response(
                                content=f"```py\n{page}\n```"
                            )
                            break

                        await self.interaction.edit_original_response(
                            content=f"```py\n{page}\n```"
                        )


class ExecModal(ui.Modal, title="Execute Shell Commands"):
    cmds = ui.TextInput(
        label="Code",
        placeholder="The command(s) to execute...",
        style=discord.TextStyle.paragraph,
    )

    bot: commands.AutoShardedBot = None
    interaction: discord.Interaction = None

    # noinspection PyBroadException
    async def on_submit(self, ctx: discord.Interaction):
        self.interaction = ctx

        # noinspection PyUnresolvedReferences
        await ctx.response.defer(thinking=True)

        proc = subprocess.run(
            self.cmds.value,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
        )

        stdout_value = proc.stdout.decode("utf-8") + proc.stderr.decode("utf-8")
        stdout_value = "\n".join(stdout_value.split("\n")[-25:])

        await self.interaction.edit_original_response(
            content="```sh\n" + stdout_value + "```"
        )


class Evaluate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # noinspection PyBroadException
    @app_commands.command(name="eval")
    @app_commands.guilds(community_server_id)
    async def _eval(self, ctx: discord.Interaction):
        if not await self.bot.is_owner(ctx.user):
            # noinspection PyUnresolvedReferences
            await ctx.response.send_message(
                content="Sorry, this is an owner(s) only command!"
            )

        modal = EvalModal()
        modal.timeout = 60
        modal.bot = self.bot

        # noinspection PyUnresolvedReferences
        await ctx.response.send_modal(modal)
        res = await modal.wait()

        if res:
            return await ctx.followup.send(
                content="Timeout! Please try again.", ephemeral=True
            )

    @app_commands.command(name="exec")
    @app_commands.guilds(community_server_id)
    async def _exec(self, ctx: discord.Interaction):
        if not await self.bot.is_owner(ctx.user):
            # noinspection PyUnresolvedReferences
            await ctx.response.send_message(
                content="Sorry, this is an owner(s) only command!"
            )

        modal = ExecModal()
        modal.timeout = 60
        modal.bot = self.bot

        # noinspection PyUnresolvedReferences
        await ctx.response.send_modal(modal)
        res = await modal.wait()

        if res:
            return await ctx.followup.send(
                content="Timeout! Please try again.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Evaluate(bot))
