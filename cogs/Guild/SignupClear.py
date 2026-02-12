import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from pathlib import Path
from helpers.Logger import Logger

# Define file paths.
SETTINGS_PATH = Path("./settings.json")
WAITLIST_FILE_PATH = Path("./data/Guild/waitlist.json")

# Utility function to load settings.
def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
        Logger.info("Loaded settings.json successfully in SignupClear command.")
        return settings
    except Exception as e:
        Logger.error("Error loading settings.json: " + str(e))
        return {}

# Utility function to save settings.
def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        Logger.info("Updated settings.json with new values in SignupClear command.")
    except Exception as e:
        Logger.error("Error saving settings.json: " + str(e))

# Utility function to load waitlist data.
def load_waitlist() -> list:
    if not WAITLIST_FILE_PATH.exists():
        Logger.info("Waitlist file does not exist. Creating a new waitlist.")
        return []
    try:
        with open(WAITLIST_FILE_PATH, "r", encoding="utf-8") as f:
            waitlist = json.load(f)
        Logger.info("Loaded waitlist data successfully in SignupClear command.")
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
        Logger.info("Saved waitlist data successfully in SignupClear command.")
    except Exception as e:
        Logger.error("Error saving waitlist.json: " + str(e))

# Function to update the original waitlist embed.
# This function re-reads the settings file so that it uses an updated waitlist_message_id and waitlist_channel_id.
async def update_waitlist_embed(bot: commands.Bot, settings: dict):
    try:
        # Reload settings to get the most up-to-date values.
        updated_settings = load_settings()
        waitlist_message_id = updated_settings.get("waitlist", {}).get("waitlist_message_id", 0)
        if waitlist_message_id == 0:
            Logger.error("Waitlist embed message ID is not set in settings.json.")
            return
        channel_id = updated_settings.get("waitlist", {}).get("waitlist_channel_id")
        if not channel_id:
            Logger.error("Waitlist channel ID is not set in settings.json.")
            return
        channel = bot.get_channel(channel_id)
        if channel is None:
            Logger.error("Waitlist channel not found during waitlist embed update.")
            return
        message = await channel.fetch_message(waitlist_message_id)
        # Prepare the updated embed content.
        embed = discord.Embed(
            title="Hateocracy 2 Guild Waitlist",
            description="Click below to sign up for the Hateocracy 2 guild waitlist",
            color=discord.Color.blue()
        )
        embed.add_field(name="Current Waitlist", value="No Players Yet...", inline=False)
        embed.set_footer(text="Players 0/30")
        # Import the original WaitlistView from the Signup cog to restore join/leave buttons.
        from cogs.Guild.Signup import WaitlistView  # Ensure the path is correct.
        view = WaitlistView(bot, updated_settings)
        await message.edit(embed=embed, view=view)
        Logger.info(f"Waitlist embed (ID: {waitlist_message_id}) updated (cleared) successfully.")
    except Exception as e:
        Logger.error("Error updating waitlist embed in SignupClear: " + str(e))

# Persistent view for confirming waitlist reset.
class ConfirmResetView(discord.ui.View):
    def __init__(self, bot: commands.Bot, settings: dict):
        # timeout=None makes the view persistent.
        super().__init__(timeout=None)
        self.bot = bot
        self.settings = settings

    @discord.ui.button(label="Confirm Waitlist Reset", style=discord.ButtonStyle.green, custom_id="confirm_waitlist_reset")
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Clear the waitlist file.
            save_waitlist([])  # Write an empty list to clear the waitlist.
            Logger.info(f"Waitlist file cleared by {interaction.user} via reset command.")
            # Update the original signup embed (restoring the join/leave buttons).
            await update_waitlist_embed(self.bot, self.settings)
            # Send an ephemeral confirmation message without delete_after (ephemeral messages auto-delete).
            await interaction.response.send_message("Waitlist has been reset.", ephemeral=True)
            Logger.info("Waitlist reset confirmed by user " + str(interaction.user))
        except Exception as e:
            Logger.error("Error in confirm_reset callback: " + str(e))
    
    async def on_timeout(self):
        pass

# Cog for the /signup-clear command.
class SignupClear(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Load settings once and cache them.
        self.settings = load_settings()
        # Cache role IDs for admin and developer from settings["guild"].
        self.admin_role = self.settings.get("guild", {}).get("admin_role")
        self.developer_role = self.settings.get("guild", {}).get("developer_role")
        # Register the persistent view for confirmation so that it works through restarts.
        self.bot.add_view(ConfirmResetView(self.bot, self.settings))

    # Slash command /signup-clear; description must be 100 characters or less.
    @app_commands.command(name="signup-clear", description="Clear the waitlist embed and data")
    async def signup_clear(self, interaction: discord.Interaction):
        # Check if the user has the admin or developer role.
        has_permission = False
        member: discord.Member = interaction.user
        for role in member.roles:
            if role.id in {self.admin_role, self.developer_role}:
                has_permission = True
                break
        if not has_permission:
            Logger.info(f"User {member} attempted to run /signup-clear without proper permissions.")
            await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
            return
        # Send an ephemeral confirmation message with the persistent reset button.
        confirm_view = ConfirmResetView(self.bot, self.settings)
        await interaction.response.send_message(
            "Are you sure you want to reset the waitlist? Click the button below to confirm.",
            view=confirm_view,
            ephemeral=True
        )
        Logger.info(f"/signup-clear command invoked by authorized user {member}.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SignupClear(bot))
    Logger.info("SignupClear cog has been loaded successfully.")