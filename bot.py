import sys
import importlib
import discord
from discord.ext import commands
from pathlib import Path
import json
import shutil
import asyncio

# Set this variable to False to disable clearing of the ./logs directory on startup.
clear_logs_on_start = True

# Clear the logs directory BEFORE the Logger is loaded.
logs_dir = Path("./logs")
if clear_logs_on_start and logs_dir.exists():
    try:
        shutil.rmtree(logs_dir)
        # Detailed log message for successful clearance of logs directory.
        print(f"[DEBUG] Cleared the logs directory: {logs_dir}")
    except Exception as e:
        print(f"[ERROR] Failed to clear logs directory {logs_dir}: {e}")

# Now import Logger after the logs directory has been cleared.
from helpers.Logger import Logger

# Enable debug logging.
Logger.set_debug(True)
Logger.info("Starting bot initialization using new settings.json structure.")

# Load settings from the settings.json file.
settings_path = Path("./settings.json")
try:
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)
    Logger.info("Settings loaded successfully from settings.json.")
except Exception as e:
    Logger.error("Failed to load settings.json: " + str(e))
    sys.exit("Something went wrong. Error Code: SETTING_LOAD_FAIL")

# Extract bot token and other settings from the new settings.json structure.
try:
    bot_token = settings["bot"]["bot_token"]
    Logger.info("Bot token loaded successfully from settings.json.")
except Exception as e:
    Logger.error("Failed to load bot token from settings.json: " + str(e))
    sys.exit("Something went wrong. Error Code: TOKEN_LOAD_FAIL")

try:
    guild_id = settings["guild"]["guild_id"]
    inactivity_channel = settings["guild"]["inactivity_channel"]
    logs_channel = settings["guild"]["logs_channel"]
    test_channel = settings["guild"]["test_channel"]
    Logger.info(f"Guild settings loaded: guild_id={guild_id}, inactivity_channel={inactivity_channel}, logs_channel={logs_channel}, test_channel={test_channel}.")
except Exception as e:
    Logger.error("Failed to load guild settings from settings.json: " + str(e))
    sys.exit("Something went wrong. Error Code: GUILD_SETTINGS_FAIL")

# Create a bot instance using commands.Bot.
intents = discord.Intents.default()
intents.message_content = True  # Ensure message content intent is enabled if needed.
bot = commands.Bot(command_prefix="!", intents=intents)

# Attach settings to the bot instance for global access.
bot.guild_id = guild_id
bot.inactivity_channel = inactivity_channel
bot.logs_channel = logs_channel
bot.test_channel = test_channel  # Making the test channel publicly accessible.

# Define a synchronous function to sync commands, using asyncio.to_thread to avoid heartbeat issues.
def SyncCommands():
    try:
        Logger.info("Syncing commands to the Bot's tree.")
        bot.tree.copy_global_to(guild=discord.Object(id=bot.guild_id))
        future = asyncio.run_coroutine_threadsafe(
            bot.tree.sync(guild=discord.Object(id=bot.guild_id)), bot.loop
        )
        future.result()
        Logger.info("Commands synced successfully!")
    except Exception as e:
        Logger.error("Error syncing commands: " + str(e))

# Event: on_ready is triggered when the bot has successfully connected.
@bot.event
async def on_ready():
    Logger.info("Bot is now ready and connected to Discord.")
    await asyncio.to_thread(SyncCommands)

# Event: on_message processes incoming messages and ensures bots are ignored.
@bot.event
async def on_message(message):
    if message.author.bot:
        Logger.debug(f"Ignored message from bot: {message.author}")
        return
    await bot.process_commands(message)

if __name__ == "__main__":
    Logger.info("Launching bot with updated settings.json configuration.")
    try:
        bot.run(bot_token)
    except Exception as e:
        Logger.error("Error occurred while running the bot: " + str(e))
        sys.exit("Something went wrong. Error Code: BOT_RUN_FAIL")