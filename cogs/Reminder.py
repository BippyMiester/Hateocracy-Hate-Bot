import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import pytz
from helpers.Logger import Logger

REMINDERS_DIR = "./data/Reminders"

class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        Logger.info("Reminder cog initialized successfully.")

    @app_commands.command(name="remindme", description="Set reminder time, timezone, and frequency for user pings")
    async def remindme(self, interaction: discord.Interaction, time: str, timezone: str, frequency: int):
        try:
            Logger.info(
                f"Received /remindme command from user {interaction.user.id} with time: {time}, timezone: {timezone}, frequency: {frequency}"
            )

            # Validate military time: 4-digit numeric string
            if not (time.isdigit() and len(time) == 4):
                Logger.error(f"Validation failed for military time input: {time} by user {interaction.user.id}")
                await interaction.response.send_message("Time must be in military format (e.g. 0400).", ephemeral=True)
                return

            # Validate timezone using pytz common timezones
            if timezone not in pytz.all_timezones:
                Logger.error(f"Validation failed for timezone input: {timezone} by user {interaction.user.id}")
                await interaction.response.send_message("Invalid timezone provided.", ephemeral=True)
                return

            # Validate frequency is a positive integer
            if frequency < 1:
                Logger.error(f"Validation failed for frequency input: {frequency} by user {interaction.user.id}")
                await interaction.response.send_message("Frequency must be a positive integer.", ephemeral=True)
                return

            # Prepare the reminder data with the new 'last_reminded' field
            reminder_data = {
                "time": time,
                "timezone": timezone,
                "frequency": frequency,
                "last_reminded": ""
            }
            Logger.info(f"Prepared reminder data for user {interaction.user.id}: {reminder_data}")

            # Ensure the reminders directory exists
            if not os.path.exists(REMINDERS_DIR):
                os.makedirs(REMINDERS_DIR, exist_ok=True)
                Logger.info(f"Created directory for reminders: {REMINDERS_DIR}")

            # Create file path for the user's reminder data file
            file_path = os.path.join(REMINDERS_DIR, f"{interaction.user.id}.json")
            
            # Write the reminder data to the file (overwrite if exists)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(reminder_data, f, indent=4)
            Logger.info(f"Successfully wrote reminder data to file: {file_path}")

            # Removed the Logger.LogDiscord call since it's not defined in Logger.py

            await interaction.response.send_message("Your reminder has been set successfully!", ephemeral=True)
        except Exception as e:
            Logger.error(f"An error occurred processing /remindme command for user {interaction.user.id}: {str(e)}")
            await interaction.response.send_message("Something went wrong. Error Code: UREM001", ephemeral=True)

    @remindme.autocomplete("timezone")
    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        # Filter through pytz.common_timezones and return matching top 25 results
        timezones = [tz for tz in pytz.common_timezones if current.lower() in tz.lower()]
        suggestions = [app_commands.Choice(name=tz, value=tz) for tz in timezones[:25]]
        Logger.info(f"Provided {len(suggestions)} autocomplete suggestions for timezone by user {interaction.user.id}")
        return suggestions

async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
    Logger.info("Reminder cog has been added to the bot successfully.")