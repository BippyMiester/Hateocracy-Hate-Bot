import os
import json
import asyncio
import datetime
import pytz
import discord
from helpers.Logger import Logger

REMINDERS_DIR = "./data/Reminders"
SETTINGS_FILE = "./settings.json"

async def run_reminder_task(bot: discord.Client):
    Logger.info("Reminder task started.")
    while True:
        try:
            # Load settings to retrieve updated config and environment details
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
                    settings = json.load(settings_file)
                Logger.info("Settings file loaded successfully for reminders task.")
            except Exception as e:
                Logger.error("Failed to load settings.json in reminders task: " + str(e))
                await asyncio.sleep(60)  # fallback sleep time if settings cannot be loaded
                continue

            # Determine environment and set detailed logging flag
            bot_env = settings.get("bot", {}).get("environment", "development")
            detailed_logging = bot_env == "development"
            reminders_settings = settings.get("reminders", {})
            if bot_env == "development":
                channel_id = reminders_settings.get("dev_channel_id")
                if detailed_logging:
                    Logger.info("Environment: development. Using dev channel id for reminders.")
            else:
                channel_id = reminders_settings.get("production_channel_id")
                if detailed_logging:
                    Logger.info("Environment: production. Using production channel id for reminders.")

            if channel_id is None:
                Logger.error("Reminder channel id not defined in settings.json.")
                await asyncio.sleep(60)
                continue

            # Retrieve the channel object using bot.get_channel
            channel = bot.get_channel(channel_id)
            if channel is None:
                Logger.error(f"Reminder channel with ID {channel_id} not found.")
                await asyncio.sleep(60)
                continue
            else:
                if detailed_logging:
                    Logger.info(f"Reminder channel (ID: {channel_id}) obtained successfully.")

            # Process reminder files only if REMINDERS_DIR exists
            if not os.path.exists(REMINDERS_DIR):
                if detailed_logging:
                    Logger.info("Reminders directory does not exist, skipping processing this iteration.")
            else:
                if detailed_logging:
                    Logger.info("Reminders directory exists, processing reminder files.")
                for filename in os.listdir(REMINDERS_DIR):
                    if detailed_logging:
                        Logger.info(f"Processing file: {filename}")
                    if not filename.endswith(".json"):
                        if detailed_logging:
                            Logger.info(f"Skipping non-JSON file: {filename}")
                        continue

                    file_path = os.path.join(REMINDERS_DIR, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            reminder_data = json.load(f)
                        if detailed_logging:
                            Logger.info(f"Loaded reminder data from {file_path}.")
                    except Exception as e:
                        Logger.error(f"Failed to load reminder file {file_path}: {str(e)}")
                        continue

                    # Extract user ID from filename
                    user_id_str = os.path.splitext(filename)[0]
                    try:
                        user_id = int(user_id_str)
                        if detailed_logging:
                            Logger.info(f"Extracted user id {user_id} from filename {filename}.")
                    except Exception as e:
                        Logger.error(f"Invalid user id in filename {filename}: {str(e)}")
                        continue

                    remind_time_str = reminder_data.get("time")
                    user_timezone_str = reminder_data.get("timezone")
                    frequency_days = reminder_data.get("frequency")
                    last_reminded_str = reminder_data.get("last_reminded", "")

                    if not (remind_time_str and user_timezone_str and frequency_days):
                        Logger.error(f"Incomplete reminder data for user {user_id} in file {filename}.")
                        continue
                    else:
                        if detailed_logging:
                            Logger.info(f"Reminder data for user {user_id}: time={remind_time_str}, timezone={user_timezone_str}, frequency={frequency_days}, last_reminded='{last_reminded_str}'")

                    try:
                        user_tz = pytz.timezone(user_timezone_str)
                        if detailed_logging:
                            Logger.info(f"Validated timezone for user {user_id}: {user_timezone_str}.")
                    except Exception as e:
                        Logger.error(f"Invalid timezone '{user_timezone_str}' for user {user_id}: {str(e)}")
                        continue

                    now_user = datetime.datetime.now(user_tz)
                    if detailed_logging:
                        Logger.info(f"Current time for user {user_id} in timezone {user_timezone_str}: {now_user.strftime('%Y-%m-%d %H:%M:%S')}")

                    # Parse the remind time (expected military format: HHMM)
                    try:
                        remind_hour = int(remind_time_str[:2])
                        remind_minute = int(remind_time_str[2:])
                        if detailed_logging:
                            Logger.info(f"Parsed remind time for user {user_id} as {remind_hour}:{remind_minute:02d}.")
                    except Exception as e:
                        Logger.error(f"Failed to parse remind time '{remind_time_str}' for user {user_id}: {str(e)}")
                        continue

                    # Set the scheduled reminder datetime for today in the user's timezone
                    scheduled_time = now_user.replace(hour=remind_hour, minute=remind_minute, second=0, microsecond=0)
                    if detailed_logging:
                        Logger.info(f"Scheduled reminder time for user {user_id}: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}.")

                    send_reminder = False

                    # Determine if we can send a reminder based on last_reminded and current time
                    if last_reminded_str == "":
                        if detailed_logging:
                            Logger.info(f"No previous reminder recorded for user {user_id}.")
                        if now_user >= scheduled_time:
                            send_reminder = True
                            if detailed_logging:
                                Logger.info(f"User {user_id} has passed scheduled time; marked for reminder.")
                        else:
                            if detailed_logging:
                                Logger.info(f"User {user_id} current time is before scheduled time; skipping reminder.")
                    else:
                        try:
                            last_reminded = datetime.datetime.fromisoformat(last_reminded_str)
                            if last_reminded.tzinfo is None:
                                last_reminded = user_tz.localize(last_reminded)
                            if detailed_logging:
                                Logger.info(f"Parsed last_reminded for user {user_id}: {last_reminded.strftime('%Y-%m-%d %H:%M:%S')}.")
                        except Exception as e:
                            Logger.error(f"Error parsing last_reminded for user {user_id}: {str(e)}")
                            continue

                        next_eligible = last_reminded + datetime.timedelta(days=frequency_days)
                        if detailed_logging:
                            Logger.info(f"Next eligible reminder time for user {user_id}: {next_eligible.strftime('%Y-%m-%d %H:%M:%S')}.")
                        if now_user >= scheduled_time and now_user >= next_eligible:
                            send_reminder = True
                            if detailed_logging:
                                Logger.info(f"User {user_id} is eligible for a reminder now.")
                        else:
                            if detailed_logging:
                                Logger.info(f"User {user_id} is not yet eligible for a reminder; skipping.")

                    if send_reminder:
                        try:
                            reminder_message = f"<@{user_id}> Hey, this is your every {frequency_days} day reminder at this time to remind you to play The Tower!"
                            await channel.send(reminder_message)
                            Logger.info(f"Reminder sent to user {user_id} in channel {channel_id}.")
                            
                            new_last_reminded = datetime.datetime.now(pytz.utc).isoformat()
                            reminder_data["last_reminded"] = new_last_reminded
                            with open(file_path, "w", encoding="utf-8") as f:
                                json.dump(reminder_data, f, indent=4)
                            Logger.info(f"Updated last_reminded for user {user_id} in file {filename}.")
                        except Exception as e:
                            Logger.error(f"Failed to send reminder for user {user_id}: {str(e)}")
                    else:
                        if detailed_logging:
                            Logger.info(f"No reminder sent for user {user_id} this iteration.")
            
            # Sleep for sleep_seconds value from settings in the reminders section; default to 60 if not set
            sleep_seconds = reminders_settings.get("sleep_seconds", 60)
            if detailed_logging:
                Logger.info(f"Iteration complete. Sleeping for {sleep_seconds} seconds before next reminder check.")
            else:
                Logger.info(f"Sleeping for {sleep_seconds} seconds.")
            await asyncio.sleep(sleep_seconds)
        except Exception as e:
            Logger.error("An unhandled exception occurred in the reminders task loop: " + str(e))
            await asyncio.sleep(60)

async def setup(bot: discord.Client):
    bot.loop.create_task(run_reminder_task(bot))
    Logger.info("Reminder task has been scheduled successfully.")