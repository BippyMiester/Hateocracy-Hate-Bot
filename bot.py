import sys
import importlib
import discord
from discord.ext import commands
from pathlib import Path
import json
import shutil

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
        # Get the bot token from the settings.json file.
        # Get guild settings from the nested guild key.
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

# Now import Logger after the logs directory has been cleared.
from helpers.Logger import Logger

# Enable debug logging.
Logger.set_debug(True)

# Clear all __pycache__ directories in the root and subdirectories.
pycache_dirs = list(Path(".").rglob("__pycache__"))
if environment == "development":
    for pycache in pycache_dirs:
        try:
            shutil.rmtree(pycache)
            Logger.debug(f"Deleted __pycache__ directory: {pycache}")
        except Exception as e:
            Logger.error(f"Failed to delete __pycache__ directory at {pycache}: {e}")

# Determine the command prefix: default to "!" if not provided by parameters.
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
        await self.LoadCogs()
        await self.LoadTasks()  # Load tasks from the tasks directory
        await self.SyncCommands()
        Logger.info("Bot is now ready and online!")
        Logger.info("-----------------------------")

    async def LoadCogs(self):
        Logger.info("Loading Cogs...")
        cogs_dir = Path("cogs")
        # Use rglob to find all .py files (except __init__.py) in the cogs directory.
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
        guild_id = self.guild_id
        Logger.info("Syncing commands to the Bot's tree")
        self.tree.copy_global_to(guild=discord.Object(id=guild_id))
        await self.tree.sync(guild=discord.Object(id=guild_id))
        Logger.info("Commands are now synced!")

client = Client()
client.guild_id = guild_id  # Assign the guild ID to the bot instance.
client.run(bot_token)