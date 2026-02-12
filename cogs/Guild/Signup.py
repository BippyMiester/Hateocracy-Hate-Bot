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
# It uses the stored waitlist_message_id and waitlist_channel_id from settings["waitlist"].
async def update_waitlist_embed(bot: commands.Bot, waitlist: list, settings: dict):
    try:
        waitlist_message_id = settings.get("waitlist", {}).get("waitlist_message_id", 0)
        channel_id = settings.get("waitlist", {}).get("waitlist_channel_id")
        if waitlist_message_id == 0 or channel_id is None:
            Logger.error("Waitlist embed message ID or channel ID is not set in settings.json.")
            return
        channel = bot.get_channel(channel_id)
        if channel is None:
            Logger.error("Waitlist channel not found during embed update.")
            return
        message = await channel.fetch_message(waitlist_message_id)
        # Construct the updated embed.
        mentions = []
        for uid in waitlist:
            user = bot.get_user(uid) or await bot.fetch_user(uid)
            mentions.append(user.mention)
        waitlist_str = "\n".join(mentions) if mentions else "No Players Yet..."
        player_count = len(waitlist)
        # Use the existing embed as a basis (or create a new one if absent).
        embed = message.embeds[0] if message.embeds else discord.Embed(
            title="Hateocracy 2 Guild Waitlist",
            description="Click below to sign up for the Hateocracy 2 guild waitlist",
            color=discord.Color.blue()
        )
        if embed.fields:
            embed.set_field_at(0, name="Current Waitlist", value=waitlist_str, inline=False)
        else:
            embed.add_field(name="Current Waitlist", value=waitlist_str, inline=False)
        embed.set_footer(text=f"Players {player_count}/30")
        # Edit the message with the updated embed and persistent view.
        await message.edit(embed=embed, view=WaitlistView(bot, settings))
        Logger.info(f"Updated waitlist embed message (ID: {waitlist_message_id}) with {player_count} player(s).")
    except Exception as e:
        Logger.error("Error updating waitlist embed: " + str(e))

# Define a view with buttons for joining and leaving the waitlist.
class WaitlistView(discord.ui.View):
    def __init__(self, bot: commands.Bot, settings: dict):
        # Set timeout to None for a persistent view.
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
            # Add the waitlist role to the user.
            waitlist_role_id = self.settings.get("waitlist", {}).get("waitlist_role")
            if waitlist_role_id and interaction.guild:
                role = interaction.guild.get_role(waitlist_role_id)
                if role:
                    await interaction.user.add_roles(role, reason="Joined waitlist")
                    Logger.info(f"Assigned waitlist role to {interaction.user}.")
                else:
                    Logger.error("Waitlist role not found in the guild.")
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
            # Remove the waitlist role from the user.
            waitlist_role_id = self.settings.get("waitlist", {}).get("waitlist_role")
            if waitlist_role_id and interaction.guild:
                role = interaction.guild.get_role(waitlist_role_id)
                if role:
                    await interaction.user.remove_roles(role, reason="Left waitlist")
                    Logger.info(f"Removed waitlist role from {interaction.user}.")
                else:
                    Logger.error("Waitlist role not found in the guild.")
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
        # Cache the admin and developer role IDs from the guild settings.
        self.admin_role = self.settings.get("guild", {}).get("admin_role")
        self.developer_role = self.settings.get("guild", {}).get("developer_role")
        # Register persistent view so that interactions persist through restarts.
        self.bot.add_view(WaitlistView(self.bot, self.settings))

    # Command to post the waitlist embed in the channel where the command was run.
    # Restricted to users with admin or developer roles.
    @app_commands.command(name="signup", description="Post waitlist embed into current channel")
    async def signup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Check if the user has admin or developer role.
        has_permission = False
        member: discord.Member = interaction.user
        for role in member.roles:
            if role.id in {self.admin_role, self.developer_role}:
                has_permission = True
                break
        if not has_permission:
            Logger.info(f"User {member} attempted to run /signup without proper permissions.")
            await interaction.followup.send("You do not have permission to perform this action.", ephemeral=True)
            return

        try:
            waitlist_message_id = self.settings.get("waitlist", {}).get("waitlist_message_id", 0)
            if waitlist_message_id != 0:
                Logger.info(f"Waitlist embed already exists with message ID {waitlist_message_id}.")
                await interaction.followup.send("Waitlist embed already exists.", ephemeral=True)
                return

            # Post embed in the channel where the command was run.
            channel = interaction.channel
            if channel is None:
                Logger.error("Channel not found when attempting to post waitlist embed.")
                await interaction.followup.send("Channel not accessible.", ephemeral=True)
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
            Logger.info(f"Posted new waitlist embed in channel {channel.id} with message ID {message.id}.")
            # Update settings.json with the new waitlist_message_id and waitlist_channel_id.
            self.settings.setdefault("waitlist", {})
            self.settings["waitlist"]["waitlist_message_id"] = message.id
            self.settings["waitlist"]["waitlist_channel_id"] = channel.id
            save_settings(self.settings)
            await interaction.followup.send("Waitlist embed posted successfully.", ephemeral=True)
        except Exception as e:
            Logger.error("Failed to post waitlist embed: " + str(e))
            await interaction.followup.send("Something went wrong. Error Code: EMBED_POST_FAIL", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Signup(bot))
    Logger.info("Signup cog has been loaded successfully.")