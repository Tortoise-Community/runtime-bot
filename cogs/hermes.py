import aiohttp
import asyncio
import discord
from decouple import config
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from typing import Dict
from utils.embed_handler import code_eval_embed, failure, info, success
from constants import bot_invite_link
from utils.logging import log_user_code

EXECUTE_URL = config("EXECUTION_API_URL")

LANG_ALIASES = {
    "py": "python",
    "python": "python",
    "js": "javascript",
    "javascript": "javascript",
    "java": "java",
}


def build_view():
    view = discord.ui.View()

    view.add_item(
        discord.ui.Button(
            label="Invite",
            emoji=discord.PartialEmoji(name="invite", id=1479091984286224487),
            url=bot_invite_link,
        )
    )

    view.add_item(
        discord.ui.Button(
            label="Star on Github",
            emoji=discord.PartialEmoji(name="github", id=1479090326709993533),
            url="https://github.com/Ryuga/Hermes",
        )
    )

    return view


class SandboxExec(commands.Cog):

    def __init__(self, bot: "MyBot"):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.tracked: Dict[int, dict] = {}
        self.execution_enabled = True

    def cog_unload(self):
        if self.cache_eviction.is_running():
            self.cache_eviction.cancel()
        self.bot.loop.create_task(self.session.close())


    def _parse_block(self, content: str):
        if not content.startswith("/run") and not content.startswith("./run"):
            return None

        if "```" not in content:
            return None

        try:
            _, block = content.split("```", 1)
            block_content = block.split("```", 1)[0]

            first_line, *rest = block_content.split("\n")
            lang = first_line.strip().lower()
            code = "\n".join(rest)

            if not lang or not code.strip():
                return None

            return lang, code, content.startswith("./run")
        except Exception:
            return None


    async def _execute(self, language: str, code: str):
        payload = {
            "language": language,
            "code": code,
        }

        async with self.session.post(EXECUTE_URL, json=payload, timeout=30) as resp:
            if resp.status == 429:
                return {
                    "code": -1,
                    "output": "",
                    "std_log": "Rate limit exceeded. Please wait before executing again.",
                    "rate_limited": True,
                }
            if resp.status == 503:
                return {
                    "code": -1,
                    "output": "",
                    "std_log": "Engine is currently under maintenance. Please try again later.",
                    "maintenance": True,
                }

            if resp.status >= 500:
                return {
                    "code": -1,
                    "output": "",
                    "std_log": "Execution engine temporarily unavailable.",
                    "unavailable": True,
                }

            return await resp.json()


    def _build_output(self, result: dict):
        exit_code = result.get("code")
        stdout = result.get("output", "") or ""
        stderr = result.get("std_log", "") or ""

        combined = stdout
        if exit_code != 0 and stderr:
            combined = combined + ("\n" if combined else "") + stderr

        if not combined:
            combined = "(no output)"

        if len(combined) > 1900:
            combined = combined[:1900] + "\n... (truncated)"

        return exit_code, combined

    async def _send_result(
        self,
        channel: discord.TextChannel,
        guild: discord.Guild,
        result: dict,
        language: str,
        edited: bool = False,
        target_message: discord.Message | None = None,
    ):
        exit_code, output = self._build_output(result)

        if result.get("rate_limited") or result.get("maintenance") or result.get("unavailable"):
            embed = failure(result.get("std_log"))
        else:
            embed = code_eval_embed(
                language,
                output,
                edited=edited,
                exit_code=exit_code,
                disable_extras=True,
            )

            embed.set_footer(
                text="Powered by Hermes Engine",
                icon_url=f"https://lairesit.sirv.com/Tortoise/{language}.png",
            )

        last_promoted = self.bot.runtime.get_last_promoted(guild.id)
        now = datetime.now(timezone.utc)

        show_view = True

        if last_promoted and now - last_promoted < timedelta(hours=1):
            show_view = False
        else:
            if not edited:
                await self.bot.runtime.set_last_promoted(guild.id, now)

        view = build_view() if show_view else None

        if target_message:
            await target_message.edit(embed=embed, view=view)
            return target_message
        else:
            return await channel.send(embed=embed, view=view)


    @tasks.loop(hours=6)
    async def cache_eviction(self):

        now = datetime.now(timezone.utc)

        expired = [
            msg_id
            for msg_id, meta in self.tracked.items()
            if now - meta["created"] > timedelta(minutes=2)
        ]

        for msg_id in expired:
            self.tracked.pop(msg_id, None)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.cache_eviction.is_running():
            self.cache_eviction.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if not self.bot.runtime.is_enabled(message.guild.id):
            return

        if self.bot.maintenance_mode:
            await message.channel.send(embed=failure("Bot is under maintenance. Please try again later."))
            return

        parsed = self._parse_block(message.content)
        if not parsed:
            return

        lang, code, minimal = parsed
        lang = LANG_ALIASES.get(lang)

        if not lang:
            await message.channel.send(
                embed=failure("Unsupported language: Use `python`, `javascript` or `java`.")
            )
            return

        async with message.channel.typing():
            try:
                result = await self._execute(lang, code)
            except Exception:
                await message.channel.send("Execution request failed.")
                return

            if minimal:
                exit_code, output = self._build_output(result)
                await message.channel.send(content=f"```ex\n{output}\n```")
                return

            bot_msg = await self._send_result(
                message.channel,
                message.guild,
                result,
                lang,
            )

            self.tracked[message.id] = {
                "created": datetime.now(timezone.utc),
                "lang": lang,
                "bot_msg_id": bot_msg.id,
            }

            asyncio.create_task(
                log_user_code(
                    self.session,
                    user_id=message.author.id,
                    code=code,
                )
            )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author.bot or not after.guild:
            return

        meta = self.tracked.get(after.id)
        if not meta:
            return

        if self.bot.maintenance_mode:
            return

        if datetime.now(timezone.utc) - meta["created"] > timedelta(minutes=2):
            self.tracked.pop(after.id, None)
            return

        parsed = self._parse_block(after.content)
        if not parsed:
            return

        lang, code, minimal = parsed
        lang = LANG_ALIASES.get(lang)

        if not lang:
            return

        async with after.channel.typing():
            try:
                result = await self._execute(lang, code)
            except Exception:
                return

            try:
                bot_msg = await after.channel.fetch_message(meta["bot_msg_id"])
            except Exception:
                return

            if minimal:
                exit_code, output = self._build_output(result)
                await bot_msg.edit(content=f"```ex\n{output}\n```")
                return

            await self._send_result(
                after.channel,
                after.guild,
                result,
                lang,
                edited=True,
                target_message=bot_msg,
            )

            asyncio.create_task(
                log_user_code(
                    self.session,
                    user_id=after.author.id,
                    code=code,
                )
            )

    @commands.command()
    async def help(self, ctx: commands.Context):
        await ctx.send(
            embed=info(
                "Commands have moved to slash commands. Use `/run_help` for more info.", self.bot.user,""
            )
        )

    @app_commands.command(name="run_help", description="Show how to run code with the execution bot")
    async def run_help(self, interaction: discord.Interaction):
        content = (
            "Run code by sending a message that starts with `/run` followed by a fenced code block.\n\n"
            "### Format:\n\n"
            "/run\n\\`\\`\\`<language>\n"
            "print(1 + 1)\n"
            "\\`\\`\\`\n\n"
            "Language support: **python**, **javascript**, **java** (**py**,**js** also works)\n"
            "### Examples\n"
            "**Python:**\n\n"
            "/run ```python\n"
            "print(1 + 1)\n"
            "```\n"
            "**JavaScript:**\n\n"
            "/run ```javascript\n"
            "console.log(1 + 1)\n"
            "```\n"
            "**Java:**\n\n"
            "/run ```java\n"
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        System.out.println(1 + 1);\n"
            "    }\n"
            "}\n"
            "// PS: Java code requires a public class to compile"
            "```\n\n"
            "**Video Explanation:**\n"
        )
        embed = info(
            content, interaction.guild.me, "How to Run Code",
            "You can edit your message within 2 minutes to re-run the code automatically."
        )
        embed.set_image(url="https://lairesit.sirv.com/Tortoise/howtoruncode.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Disable runtime execution in this guild")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable_runtime(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        await self.bot.runtime.set_enabled(interaction.guild.id, False)
        await interaction.followup.send(embed=success("Runtime Disabled"))

    @app_commands.command(description="Enable runtime execution in this guild")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable_runtime(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        await self.bot.runtime.set_enabled(interaction.guild.id, True)
        await interaction.followup.send(embed=success("Runtime Enabled"))

    @app_commands.command(description="Get invite link for the bot")
    async def invite(self, interaction: discord.Interaction):

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Invite Bot",
                description="Click the button below to invite the bot to your server.",
                color=discord.Color.green()
            ),
            view=build_view(),
            ephemeral=False
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(SandboxExec(bot))
