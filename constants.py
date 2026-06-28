from discord import Color

tortoise_guild_id = 1520372691448889364
website_url = "https://www.tortoisecommunity.org/"
github_repo_link = "https://github.com/Ryuga/Hermes"
bot_repo_link = "https://github.com/Tortoise-Community/Runtime-BOT"
discord_invite_link = "https://discord.gg/WeUtJ7hqum"
bot_invite_link = "https://discord.com/oauth2/authorize?client_id=780132667265122315"
tortoise_community_avatar_link = "https://avatars.githubusercontent.com/u/54438042"

# Log Channel IDs
system_log_channel_id = 1520372692090359891

# Roles
moderator_role = 1520372691469729959
admin_role = 1520372691486638113

# Emojis
success_emoji = "<a:success:1479072071064490069>"
failure_emoji = "<a:failure:1479072121261920316>"

# Special
tortoise_developers = (197918569894379520, 612349409736392928)

# Embeds are not monospaced so we need to use spaces to make different lines "align"
# But discord doesn't like spaces and strips them down.
# Using a combination of zero width space + regular space solves stripping problem.
embed_space = "\u200b "

# After this is exceeded the link to tortoise paste service should be sent
max_message_length = 1000

rate_limit_minutes = 10

accent_color = 0x98DFAF