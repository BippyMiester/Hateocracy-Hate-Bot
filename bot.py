import sys
import importlib
import discord
from discord.ext import commands
from pathlib import Path
import json
import shutil
import asyncio
# Now import Logger after the logs directory has been cleared.
from helpers.Logger import Logger
Logger.set_debug(True)

# Set a custom NLTK data path and add it to NLTK paths.
NLTK_DATA_PATH = Path(".\\.venv\\nltk_data")
import nltk
nltk.data.path.append(str(NLTK_DATA_PATH))

# Load settings from settings.json.
settings_path = Path("./settings.json")
with open(settings_path, "r", encoding="utf-8") as f:
    settings = json.load(f)
    # Get bot environment
    environment = settings["bot"]["environment"]
    
    if environment == "development":
        # Get the bot token from the settings.json file.
        bot_token = settings["bot"]["bot_token_development"]
        guild_id = settings["guild_development"]["guild_id"]
    else:
        # Get the bot token from settings.json.
        bot_token = settings["bot"]["bot_token_production"]
        guild_id = settings["guild_production"]["guild_id"]

# Clear the logs directory BEFORE the Logger is loaded.
logs_dir = Path("./logs")
if environment == "development":
    try:
        shutil.rmtree(logs_dir)
        print(f"Cleared the logs directory: {logs_dir}")
    except Exception as e:
        print(f"Failed to clear logs directory {logs_dir}: {e}")

# Clear all __pycache__ directories in the root and subdirectories.
pycache_dirs = list(Path(".").rglob("__pycache__"))
if environment == "development":
    for pycache in pycache_dirs:
        try:
            shutil.rmtree(pycache)
            Logger.debug(f"Deleted __pycache__ directory: {pycache}")
        except Exception as e:
            Logger.error(f"Failed to delete __pycache__ directory at {pycache}: {e}")

# Determine the command prefix: default to "!".
command_prefix = "!"

class Client(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.guilds = True
        intents.reactions = True
        intents.message_content = True
        intents.members = True
        self.youtube_credentials = None
        super().__init__(command_prefix=command_prefix, intents=intents)

    async def on_ready(self):
        Logger.info("-----------------------------")
        Logger.info("Starting bot...")
        Logger.info(f"User: {self.user}")
        Logger.info(f"ID: {self.user.id}")
        Logger.info(f"Command Prefix: {command_prefix}")
        Logger.info("-----------------------------")
        
        # Do basic Discord Stuff
        await self.LoadCogs()
        await self.LoadTasks()  # Load tasks from the tasks directory
        await self.SyncCommands()
        
        # Handle NLTK Downloads
        await self.DownloadNLTKData()

        Logger.info("Bot is now ready and online!")
        Logger.info("-----------------------------")

    async def LoadCogs(self):
        Logger.info("Loading Cogs...")
        cogs_dir = Path("cogs")
        # Iterate through all .py files (except __init__.py) in the cogs directory.
        for cog_file in cogs_dir.rglob("*.py"):
            if cog_file.name != "__init__.py":
                relative_parts = cog_file.with_suffix("").relative_to(cogs_dir).parts
                module_name = "cogs." + ".".join(relative_parts)
                Logger.debug(f"Trying to load cog: {module_name}")
                try:
                    await self.load_extension(module_name)
                    Logger.debug(f"Loaded cog from file: {module_name}")
                except Exception as e:
                    Logger.error(f"Failed to load cog {module_name}: {e}")
        Logger.info("Cogs are loaded!")

    async def LoadTasks(self):
        Logger.info("Loading Tasks...")
        tasks_dir = Path("tasks")
        for task_file in tasks_dir.rglob("*.py"):
            if task_file.name != "__init__.py":
                relative_parts = task_file.with_suffix("").relative_to(tasks_dir).parts
                module_name = "tasks." + ".".join(relative_parts)
                Logger.debug(f"Trying to load task: {module_name}")
                try:
                    await self.load_extension(module_name)
                    Logger.debug(f"Loaded task from file: {module_name}")
                except Exception as e:
                    Logger.error(f"Failed to load task {module_name}: {e}")
        Logger.info("Tasks are loaded!")

    async def SyncCommands(self):
        Logger.info("Syncing commands to the Bot's tree")
        Logger.info("Copying Global To Guild")
        self.tree.copy_global_to(guild=discord.Object(id=guild_id))
        if environment == "production":
            Logger.warning("Bot is in PRODUCTION mode, syncing to Discord servers.")
            await self.tree.sync(guild=discord.Object(id=guild_id))
        else:
            Logger.info("Bot is in DEVELOPMENT mode, skipping sync to Discord servers.")
        Logger.info("Commands are now synced!")

    async def DownloadNLTKData(self):
        Logger.info(f"Downloading NLTK resources to {NLTK_DATA_PATH}...")
        await asyncio.to_thread(nltk.download, 'all', download_dir=str(NLTK_DATA_PATH), quiet=True)
        Logger.info("NLTK resources downloaded successfully.")

    async def on_message(self, message):
        Logger.debug(f"Received message from {message.author} in channel {message.channel.id}")
        try:
            # Prevent responding to its own messages.
            if message.author == self.user:
                return

            # Determine target channel id from the ai section based on the environment.
            if environment == "development":
                target_channel_id = settings["ai"].get("development_channel")
            else:
                target_channel_id = settings["ai"].get("production_channel")
                
            Logger.debug(f"Target AI channel id is {target_channel_id} for environment {environment}")

            if message.channel.id == target_channel_id:
                Logger.info(f"Message received in target channel {target_channel_id}; invoking AITask.pong for user {message.author}")
                AI = self.get_cog("AITask")
                if AI:
                    await AI.pong(message)
                else:
                    Logger.error("AITask cog not loaded.")
        except Exception as e:
            Logger.error(f"Error processing on_message event: {e}")
        # Ensure commands still get processed.
        await self.process_commands(message)

client = Client()
client.guild_id = guild_id  # Assign the guild ID to the bot instance.
client.run(bot_token)