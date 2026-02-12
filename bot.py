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
        print(f"Cleared the logs directory: {logs_dir}")
    except Exception as e:
        print(f"Failed to clear logs directory {logs_dir}: {e}")

# Now import Logger after the logs directory has been cleared.
from helpers.Logger import Logger

# Enable debug logging.
Logger.set_debug(True)
Logger.info("Starting bot initialization.")

# Load settings from settings.json.
settings_path = Path("./settings.json")
try:
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)
    Logger.info("Loaded settings from settings.json successfully.")
except Exception as e:
    Logger.error("Failed to load settings.json: " + str(e))
    sys.exit("Settings loading failed.")

# Extract bot token from the settings.json file.
try:
    bot_token = settings["bot"]["bot_token"]
    Logger.info("Bot token loaded successfully from settings.json.")
except Exception as e:
    Logger.error("Failed to load bot token from settings.json: " + str(e))
    sys.exit("Bot token missing.")

# Extract guild settings from the settings.json file.
try:
    guild_id = settings["guild"]["guild_id"]
    inactivity_channel = settings["guild"]["inactivity_channel"]
    logs_channel = settings["guild"]["logs_channel"]
    Logger.info(f"Guild settings loaded successfully: guild_id={guild_id}, inactivity_channel={inactivity_channel}, logs_channel={logs_channel}")
except Exception as e:
    Logger.error("Failed to load guild settings from settings.json: " + str(e))
    sys.exit("Guild settings missing.")

# Create a bot instance using commands.Bot.
intents = discord.Intents.default()
intents.message_content = True  # Ensure message content intent is enabled if needed.
bot = commands.Bot(command_prefix="!", intents=intents)

# Attach settings to the bot instance for global access.
bot.guild_id = guild_id
bot.inactivity_channel = inactivity_channel
bot.logs_channel = logs_channel

# Define a synchronous function to sync commands via asyncio.to_thread.
def SyncCommands():
    try:
        Logger.info("Syncing commands to the Bot's tree.")
        bot.tree.copy_global_to(guild=discord.Object(id=bot.guild_id))
        # Running the coroutine in the event loop using asyncio.run_coroutine_threadsafe.
        future = asyncio.run_coroutine_threadsafe(
            bot.tree.sync(guild=discord.Object(id=bot.guild_id)), bot.loop
        )
        future.result()
        Logger.info("Commands are now synced!")
    except Exception as e:
        Logger.error("Error syncing commands: " + str(e))

# Event: on_ready indicates the bot has successfully connected.
@bot.event
async def on_ready():
    Logger.info("Bot is now ready and connected to Discord.")
    await asyncio.to_thread(SyncCommands)

# Event: on_message to process commands but ignore messages from bots.
@bot.event
async def on_message(message):
    if message.author.bot:
        Logger.debug(f"Ignoring message from bot: {message.author}")
        return
    await bot.process_commands(message)

if __name__ == "__main__":
    Logger.info("Launching bot...")
    try:
        bot.run(bot_token)
    except Exception as e:
        Logger.error("Error occurred while running the bot: " + str(e))
        sys.exit("Bot terminated due to an error.")