import itertools
import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils.checks import tortoise_bot_developer_only
from constants import tortoise_guild_id
from utils.embed_handler import success, failure, info


class BroadcastModal(discord.ui.Modal, title="Send Embed"):

    title_input = discord.ui.TextInput(
        label="Title",
        required=True,
        max_length=256
    )

    description_input = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        required=True
    )

    footer_input = discord.ui.TextInput(
        label="Footer (optional)",
        required=False,
        max_length=256
    )

    def __init__(self, bot, guild_id: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = self.bot.get_guild(self.guild_id)

        if not guild:
            await interaction.followup.send(embed=failure("Guild not found."))
            return

        embed = discord.Embed(
            title=self.title_input.value,
            description=self.description_input.value,
            color=discord.Color.dark_green()
        )

        if self.footer_input.value:
            embed.set_footer(text=self.footer_input.value)

        sent = False

        for channel in guild.text_channels:
            try:
                await channel.send(embed=embed)
                sent = True
                break
            except:
                continue

        if sent:
            await interaction.followup.send(embed=success("Message sent."), ephemeral=True)
        else:
            await interaction.followup.send(embed=failure("Failed to send message."), ephemeral=True)


class MasterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.statuses = [
            "/run to execute code",
        ]

        self.status_cycle = itertools.cycle(self.statuses)

    async def cog_load(self):
        self.change_status.start()

    async def cog_unload(self):
        self.change_status.cancel()


    @tasks.loop(seconds=50)
    async def change_status(self):
        if not self.statuses:
            return

        await self.bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.competing,
                name=next(self.status_cycle),
                # url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            ),
        )

    @change_status.before_loop
    async def before_change_status(self):
        await self.bot.wait_until_ready()


    master_group = app_commands.Group(
        name="master",
        description="Master commands",
        guild_ids=[tortoise_guild_id]
    )

    @master_group.command(name="status_add", description="Add a rotating status")
    @app_commands.check(tortoise_bot_developer_only)
    async def status_add(self, interaction: discord.Interaction, status: str):
        self.statuses.append(status)
        self.status_cycle = itertools.cycle(self.statuses)

        await interaction.response.send_message(
            f"✅ **Status added:**\n`{status}`",
            ephemeral=True,
        )

    @master_group.command(name="status_remove", description="Remove a rotating status")
    @app_commands.check(tortoise_bot_developer_only)
    async def status_remove(self, interaction: discord.Interaction, status: str):
        if status not in self.statuses:
            await interaction.response.send_message(
                "❌ That status does not exist.",
                ephemeral=True,
            )
            return

        self.statuses.remove(status)
        self.status_cycle = itertools.cycle(self.statuses)

        await interaction.response.send_message(
            f"🗑️ **Status removed:**\n`{status}`",
            ephemeral=True,
        )

    @master_group.command(name="status_list", description="List all rotating statuses")
    @app_commands.check(tortoise_bot_developer_only)
    async def status_list(self, interaction: discord.Interaction):
        formatted = "\n".join(
            f"{i + 1}. {s}" for i, s in enumerate(self.statuses)
        )

        await interaction.response.send_message(
            f"📊 **Current Statuses:**\n{formatted}",
            ephemeral=True,
        )

    @master_group.command(name="enable_maintenance", description="Enable maintenance mode")
    @app_commands.check(tortoise_bot_developer_only)
    async def enable_maintenance(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.bot.maintenance_mode = True
        await interaction.followup.send(
            embed=success("Maintenance mode enabled.")
        )

    @master_group.command(name="disable_maintenance", description="Disable maintenance mode")
    @app_commands.check(tortoise_bot_developer_only)
    async def disable_maintenance(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.bot.maintenance_mode = False
        await interaction.followup.send(
            embed=success("Maintenance mode disabled.")
        )

    @master_group.command(name="list_guilds", description="List all guilds")
    @app_commands.check(tortoise_bot_developer_only)
    async def list_guilds(self, interaction: discord.Interaction):
        guilds = self.bot.guilds

        if not guilds:
            await interaction.response.send_message("No guilds found.")
            return

        await interaction.response.defer()

        lines = []

        for guild in guilds:
            invite_link = "No invite"

            for channel in guild.text_channels:
                try:
                    invite = await channel.create_invite(max_age=300, max_uses=1)
                    invite_link = invite.url
                    break
                except:
                    continue

            lines.append(f"{guild.name} (ID: {guild.id}) → {invite_link}")

        await interaction.followup.send("\n".join(lines))


    @master_group.command(name="broadcast", description="Send embed to a specific guild")
    @app_commands.check(tortoise_bot_developer_only)
    @app_commands.describe(guild_id="Target guild ID")
    async def broadcast(self, interaction: discord.Interaction, guild_id: str):
        try:
            guild_id = int(guild_id)
        except ValueError:
            await interaction.response.send_message(embed=failure("Invalid guild ID."), ephemeral=True)
            return

        await interaction.response.send_modal(
            BroadcastModal(self.bot, guild_id)
    )

    @master_group.command(name="leave_guild", description="Send goodbye and leave a guild")
    @app_commands.check(tortoise_bot_developer_only)
    @app_commands.describe(
        guild_id="Target guild ID",
        reason="Reason for leaving"
    )
    async def leave_guild(self, interaction: discord.Interaction, guild_id: str, reason: str):
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = int(guild_id)
        except ValueError:
            await interaction.followup.send(embed=failure("Invalid guild ID."))
            return

        guild = self.bot.get_guild(guild_id)

        if not guild:
            await interaction.followup.send(embed=failure("Guild not found."))
            return

        embed = discord.Embed(
            title="Goodbye 👋",
            description=f"I am leaving this server.\n\n**Reason:** {reason}"
        )

        sent = False

        for channel in guild.text_channels:
            try:
                await channel.send(embed=embed)
                sent = True
                break
            except:
                continue

        try:
            await guild.leave()

            if sent:
                await interaction.followup.send(embed=success("Message sent and left the guild."))
            else:
                await interaction.followup.send(embed=failure("Left guild, but failed to send message."))
        except Exception as e:
            await interaction.followup.send(embed=failure(f"Failed to leave guild: {e}"))

    @master_group.command(name="give_pro", description="Grant pro access to a guild")
    @app_commands.check(tortoise_bot_developer_only)
    @app_commands.describe(guild_id="Target guild ID")
    async def give_pro(self, interaction: discord.Interaction, guild_id: str):
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = int(guild_id)
        except ValueError:
            await interaction.followup.send(embed=failure("Invalid guild ID."))
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            await interaction.followup.send(embed=failure("Guild not found."))
            return

        await self.bot.runtime.set_pro(guild_id, True)

        embed = info(
                "# <:pro:1503090301001011340> Pro Access Enabled\n\n"
                "This server has been given **Pro access**.\n\n"
                "This is **not a paid feature**. The bot is completely free for everyone.\n"
                "Some language execution features require elevated permissions, which is why Pro exists.\n\n"
                "You now have access to those extended capabilities.",
                self.bot.user,
            "",
            "Tortoise Programming Community"
        )

        sent = False
        if guild.system_channel:
            try:
                await guild.system_channel.send(embed=embed)
                sent = True
            except:
                pass

        await interaction.followup.send(
            embed=success("Pro granted." + (" Notification sent." if sent else " Could not send notification."))
        )

    @master_group.command(name="remove_pro", description="Remove pro access from a guild")
    @app_commands.check(tortoise_bot_developer_only)
    @app_commands.describe(guild_id="Target guild ID")
    async def remove_pro(self, interaction: discord.Interaction, guild_id: str):
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = int(guild_id)
        except ValueError:
            await interaction.followup.send(embed=failure("Invalid guild ID."))
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            await interaction.followup.send(embed=failure("Guild not found."))
            return

        await self.bot.runtime.set_pro(guild_id, False)

        await interaction.followup.send(
            embed=success("Pro removed.")
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(MasterCog(bot))
