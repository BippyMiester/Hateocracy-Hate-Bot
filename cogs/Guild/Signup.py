import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import os
from pathlib import Path
from helpers.Logger import Logger

# Define the file paths.
SETTINGS_PATH = Path("./settings.json")
WAITLIST_FILE_PATH = Path("./data/Guild/waitlist.json")

# Utility function to load settings.
def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
        Logger.info("Loaded settings.json successfully in Signup command.")
        return settings
    except Exception as e:
        Logger.error("Error loading settings.json: " + str(e))
        return {}

# Utility function to save settings.
def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        Logger.info("Updated settings.json with new values.")
    except Exception as e:
        Logger.error("Error saving settings.json: " + str(e))

# Utility function to load waitlist data.
def load_waitlist() -> list:
    if not WAITLIST_FILE_PATH.exists():
        Logger.info("Waitlist file does not exist. Creating new waitlist.")
        return []
    try:
        with open(WAITLIST_FILE_PATH, "r", encoding="utf-8") as f:
            waitlist = json.load(f)
        Logger.info("Loaded waitlist data successfully.")
        return waitlist
    except Exception as e:
        Logger.error("Error loading waitlist.json: " + str(e))
        return []

# Utility function to save waitlist data.
def save_waitlist(waitlist: list) -> None:
    try:
        os.makedirs(WAITLIST_FILE_PATH.parent, exist_ok=True)
        with open(WAITLIST_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(waitlist, f, indent=4)
        Logger.info("Saved waitlist data successfully.")
    except Exception as e:
        Logger.error("Error saving waitlist.json: " + str(e))

# Function to update the waitlist embed message.
async def update_waitlist_embed(bot: commands.Bot, waitlist: list, settings: dict):
    try:
        # Get the waitlist_message_id and test_channel from the cached settings.
        waitlist_message_id = settings.get("guild", {}).get("waitlist_message_id", 0)
        if waitlist_message_id == 0:
            Logger.error("Waitlist embed message ID is not set in settings.json.")
            return

        test_channel_id = settings.get("guild", {}).get("test_channel")
        channel = bot.get_channel(test_channel_id)
        if channel is None:
            Logger.error("Test channel not found during waitlist embed update.")
            return

        message = await channel.fetch_message(waitlist_message_id)
        # Construct the updated embed.
        mentions = []
        for uid in waitlist:
            user = bot.get_user(uid) or await bot.fetch_user(uid)
            mentions.append(user.mention)
        waitlist_str = "\n".join(mentions) if mentions else "No Players Yet..."
        player_count = len(waitlist)
        # Create a new embed using the current embed as basis.
        embed = message.embeds[0]
        embed_dict = embed.to_dict()
        if "fields" in embed_dict and embed_dict["fields"]:
            embed_dict["fields"][0]["value"] = waitlist_str
        else:
            embed_dict["fields"] = [{"name": "Current Waitlist", "value": waitlist_str, "inline": False}]
        embed_dict["footer"] = {"text": f"Players {player_count}/30"}
        new_embed = discord.Embed.from_dict(embed_dict)
        await message.edit(embed=new_embed, view=WaitlistView(bot, settings))
        Logger.info(f"Updated waitlist embed message (ID: {waitlist_message_id}) with {player_count} player(s).")
    except Exception as e:
        Logger.error("Error updating waitlist embed: " + str(e))

# Define a view with buttons for joining and leaving the waitlist.
class WaitlistView(discord.ui.View):
    def __init__(self, bot: commands.Bot, settings: dict):
        # Set timeout to None for persistent view and ensure buttons have custom_ids for persistence.
        super().__init__(timeout=None)
        self.bot = bot
        self.settings = settings

    @discord.ui.button(label="Join Waitlist", style=discord.ButtonStyle.green, custom_id="join_waitlist")
    async def join_waitlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            waitlist = load_waitlist()
            user_id = interaction.user.id
            if user_id in waitlist:
                Logger.info(f"User {interaction.user} attempted to join waitlist but is already in it.")
                await interaction.response.send_message("You are already in the waitlist.", ephemeral=True)
                return
            waitlist.append(user_id)
            save_waitlist(waitlist)
            Logger.info(f"User {interaction.user} added to waitlist.")
            # Update the embed message using cached settings.
            await update_waitlist_embed(self.bot, waitlist, self.settings)
            await interaction.response.send_message("You have joined the waitlist.", ephemeral=True)
        except Exception as e:
            Logger.error("Error in join_waitlist callback: " + str(e))
            await interaction.response.send_message("Something went wrong. Error Code: JOIN_FAIL", ephemeral=True)

    @discord.ui.button(label="Leave Waitlist", style=discord.ButtonStyle.red, custom_id="leave_waitlist")
    async def leave_waitlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            waitlist = load_waitlist()
            user_id = interaction.user.id
            if user_id not in waitlist:
                Logger.info(f"User {interaction.user} attempted to leave waitlist but was not in it.")
                await interaction.response.send_message("You are not in the waitlist.", ephemeral=True)
                return
            waitlist.remove(user_id)
            save_waitlist(waitlist)
            Logger.info(f"User {interaction.user} removed from waitlist.")
            # Update the embed message using cached settings.
            await update_waitlist_embed(self.bot, waitlist, self.settings)
            await interaction.response.send_message("You have left the waitlist.", ephemeral=True)
        except Exception as e:
            Logger.error("Error in leave_waitlist callback: " + str(e))
            await interaction.response.send_message("Something went wrong. Error Code: LEAVE_FAIL", ephemeral=True)

class Signup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Load settings only once and store them.
        self.settings = load_settings()
        # Cache the test channel ID from the settings.
        self.test_channel = self.settings.get("guild", {}).get("test_channel")
        # Register persistent view so that interactions for the waitlist persist through restarts.
        self.bot.add_view(WaitlistView(self.bot, self.settings))

    # Command to post the waitlist embed in the test channel if not already posted.
    @app_commands.command(name="signup", description="Post waitlist embed into test channel")
    async def signup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            waitlist_message_id = self.settings.get("guild", {}).get("waitlist_message_id", 0)
            # Check if the embed has already been posted.
            if waitlist_message_id != 0:
                Logger.info(f"Waitlist embed already exists with message ID {waitlist_message_id}.")
                await interaction.followup.send("Waitlist embed already exists.", ephemeral=True)
                return

            channel = self.bot.get_channel(self.test_channel)
            if channel is None:
                Logger.error("Test channel not found when attempting to post waitlist embed.")
                await interaction.followup.send("Test channel not accessible.", ephemeral=True)
                return

            # Create the waitlist embed.
            embed = discord.Embed(
                title="Hateocracy 2 Guild Waitlist",
                description="Click below to sign up for the Hateocracy 2 guild waitlist",
                color=discord.Color.blue()
            )
            embed.add_field(name="Current Waitlist", value="No Players Yet...", inline=False)
            embed.set_footer(text="Players 0/30")

            view = WaitlistView(self.bot, self.settings)
            message = await channel.send(embed=embed, view=view)
            Logger.info(f"Posted new waitlist embed in test channel with message ID {message.id}.")

            # Update settings.json with the new waitlist_message_id.
            self.settings["guild"]["waitlist_message_id"] = message.id
            save_settings(self.settings)
            await interaction.followup.send("Waitlist embed posted successfully.", ephemeral=True)
        except Exception as e:
            Logger.error("Failed to post waitlist embed: " + str(e))
            await interaction.followup.send("Something went wrong. Error Code: EMBED_POST_FAIL", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Signup(bot))
    Logger.info("Signup cog has been loaded successfully.")