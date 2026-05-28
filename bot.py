import subprocess
import asyncio
import discord
from decouple import config
from discord.ext import commands

from utils.embed_handler import simple_embed
from utils.manager import RuntimeManager, Database
from constants import system_log_channel_id, discord_invite_link, tortoise_guild_id, bot_repo_link

TOKEN = config("DISCORD_BOT_TOKEN")
DB_URL = config("DATABASE_URL")


class MyBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        super().__init__(
            command_prefix=None,
            intents=intents,
            max_messages=0,
            member_cache_flags=discord.MemberCacheFlags.none(),
            chunk_guilds_at_startup=False,
            help_command=None
        )

        self.db = Database(DB_URL)
        self.runtime: RuntimeManager | None = None
        self.build_version = None
        self.maintenance_mode = False
        self.dev_mode = False

    async def setup_hook(self):

        await self.db.connect()

        self.runtime = RuntimeManager(self.db)
        await self.runtime.setup()
        await self.runtime.load_cache()

        # Cogs
        await self.load_extension("cogs.hermes")
        await self.load_extension("cogs.logger")
        await self.load_extension("cogs.master")
        # await self.load_extension("cogs.health")

        await self.tree.sync()
        try:
            await self.tree.sync(guild=discord.Object(id=tortoise_guild_id))
        except discord.errors.Forbidden:
            self.dev_mode = True
            print("⚙️ Development mode active")

        print("✅ Synced application commands")


bot = MyBot()

async def send_restart_message(client: commands.Bot):
    try:
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        commit_hash = config("BOT_BUILD_VERSION", "mystery-build")

    channel = client.get_channel(system_log_channel_id)
    client.build_version = commit_hash

    if channel is None:
        return

    try:
        commit = f"[{commit_hash}]({bot_repo_link}/commit/{commit_hash})"
        embed = simple_embed(message=f"Build version: {commit}", title="")
        embed.set_footer(text=f"🔄 Bot Restarted")
        await channel.send(
            embed=embed,
        )
    except discord.Forbidden:
        pass

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    print("APP COMMAND ERROR:", error)

    if not interaction.response.is_done():
        await interaction.response.send_message(
            "Command failed.",
            ephemeral=True
        )

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    await send_restart_message(bot)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.guild is None:
        try:
            await message.channel.send(
                f"Need Support? Join 👉 {discord_invite_link}"
            )
        except discord.Forbidden:
            pass
        return

    await bot.process_commands(message)


async def main():
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
