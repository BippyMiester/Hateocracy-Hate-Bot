import discord
from discord.ext import commands
import json
from pathlib import Path
import asyncio
import datetime
import re
import openai
from openai import OpenAI  # Import the new OpenAI client
from helpers.Logger import Logger

def parse_timeout(duration_str: str) -> datetime.timedelta:
    """
    Parse a duration string formatted as a number followed by 'm', 'h', or 'd'
    into a datetime.timedelta object.
    Example: "1m" -> 1 minute, "2h" -> 2 hours, "3d" -> 3 days.
    Returns None if parsing fails.
    """
    match = re.match(r"(\d+)([mhd])", duration_str)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return datetime.timedelta(minutes=value)
    elif unit == "h":
        return datetime.timedelta(hours=value)
    elif unit == "d":
        return datetime.timedelta(days=value)
    return None

class AutoModeration(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot
        # Load moderation settings from settings.json.
        settings_path = Path("./settings.json")
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            self.mod_settings = settings.get("moderation", {})
            self.environment = settings["bot"]["environment"]
            # Get the OpenAI API key from the "tokens" section.
            self.openai_api_key = settings["tokens"].get("openai_api_key")
            Logger.info("AutoModeration settings loaded successfully.")
        except Exception as e:
            Logger.error(f"Error loading moderation settings: {e}")
            self.mod_settings = {}
            self.environment = "development"
            self.openai_api_key = None

    async def process_moderation(self, message: discord.Message):
        Logger.debug(f"Starting AutoModeration for message {message.id} from {message.author}")
        
        # Check if the message author is excluded.
        excluded_users = self.mod_settings.get("excluded_users", [])
        if message.author.id in excluded_users:
            Logger.debug(f"Message {message.id} author {message.author.id} is excluded from moderation.")
            return

        # Check if the message is in any excluded channel.
        excluded_channels = self.mod_settings.get("excluded_channels", [])
        if message.channel.id in excluded_channels:
            Logger.debug(f"Message {message.id} is in an excluded channel: {message.channel.id}")
            return

        # Check if the message is in any excluded category.
        excluded_categories = self.mod_settings.get("excluded_categories", [])
        if message.channel.category and message.channel.category.id in excluded_categories:
            Logger.debug(f"Message {message.id} is in an excluded category: {message.channel.category.id}")
            return

        # Construct payload for moderation API.
        payload = f"UserID: {message.author.id}\nMessage: {message.content}"
        Logger.debug(f"Payload for moderation: {payload}")

        # Call OpenAI Moderation endpoint using new OpenAI library syntax.
        try:
            client = OpenAI(api_key=self.openai_api_key)
            response = await asyncio.to_thread(
                lambda: client.moderations.create(
                    model=self.mod_settings.get("model", "omni-moderation-latest"),
                    input=payload
                )
            )
            Logger.debug(f"OpenAI moderation response: {response}")
        except Exception as e:
            Logger.error(f"Error calling OpenAI Moderation API: {e}")
            return

        # Parse the moderation result.
        try:
            result = response.results[0]
        except Exception as e:
            Logger.error(f"Error parsing moderation response for message {message.id}: {e}")
            return

        # Logging full flagged categories and scores.
        full_flagged = {}
        for cat, flagged in result.categories.__dict__.items():
            if flagged:
                score = result.category_scores.__dict__.get(cat)
                full_flagged[cat] = score
        Logger.info(f"Full flagged categories for message {message.id}: {full_flagged}")

        # Retrieve additional settings.
        min_score = self.mod_settings.get("minimum_category_score", 0.85)
        ignored_categories = self.mod_settings.get("ignored_categories", [])
        
        # Iterate over all flagged categories and decide which ones are applicable.
        applicable_categories = []
        flagged_scores_dict = {}
        skipped_categories = {}
        for cat, flagged in result.categories.__dict__.items():
            if flagged:
                score = result.category_scores.__dict__.get(cat)
                if cat in ignored_categories:
                    skipped_categories[cat] = "ignored"
                    continue
                if score is None:
                    skipped_categories[cat] = "no score available"
                    continue
                # Only consider as violation if score is between min_score (inclusive) and less than 1.0.
                if min_score <= score < 1.0:
                    applicable_categories.append(cat)
                    flagged_scores_dict[cat] = score
                else:
                    skipped_categories[cat] = f"score {score} not in range [{min_score}, 1.0)"
        
        Logger.info(f"Applicable categories for message {message.id}: {applicable_categories} with scores: {flagged_scores_dict}")
        Logger.info(f"Skipped categories during filtering for message {message.id}: {skipped_categories}")

        if not applicable_categories:
            Logger.debug(f"Message {message.id} passed moderation after filtering categories.")
            return

        violation_reason = ", ".join(applicable_categories)
        Logger.info(f"Message {message.id} flagged for violation: {violation_reason} | Scores: {flagged_scores_dict}")

        # Check if dm_user is true before sending a DM.
        if self.mod_settings.get("dm_user", True):
            try:
                rules_channel_id = self.mod_settings.get("rules_channel")
                rules_channel_mention = f"<#{rules_channel_id}>" if rules_channel_id else "the rules channel"
                dm_embed = discord.Embed(
                    title="Moderation Warning",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.utcnow()
                )
                dm_embed.add_field(name="Notice", value="Your message violated our moderation policies.", inline=False)
                dm_embed.add_field(name="Rules", value=f"Please review the rules here: {rules_channel_mention}", inline=False)
                dm_embed.add_field(name="Original Message", value=message.content, inline=False)
                dm_embed.add_field(name="Reason", value=violation_reason, inline=False)
                await message.author.send(embed=dm_embed)
                Logger.info(f"Sent DM warning embed to user {message.author.id} for message {message.id}")
            except Exception as e:
                Logger.error(f"Failed to send DM warning to user {message.author.id}: {e}")
        else:
            Logger.debug(f"DMing disabled; not sending warning to user {message.author.id}")

        # Prepare to update user's moderation violation file.
        mod_data_dir = Path("./data/moderation")
        mod_data_dir.mkdir(parents=True, exist_ok=True)
        user_file = mod_data_dir / f"{message.author.id}.json"
        violations = []
        if user_file.exists():
            try:
                with open(user_file, "r", encoding="utf-8") as f:
                    violations = json.load(f)
            except Exception as e:
                Logger.error(f"Error reading moderation file for user {message.author.id}: {e}")
        previous_violations_count = len(violations)
        current_violation_number = previous_violations_count + 1

        # Logging the violation in an embed.
        if self.mod_settings.get("logging_enabled", True):
            if self.environment == "development":
                log_channel_id = self.mod_settings.get("logging_channel_development")
            else:
                log_channel_id = self.mod_settings.get("logging_channel_production")
            log_channel = self.bot.get_channel(log_channel_id)
            violation_time = datetime.datetime.utcnow().isoformat() + " UTC"
            msg_link = (f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                        if message.guild else "N/A")
            log_embed = discord.Embed(
                title="Moderation Violation",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            log_embed.add_field(name="User", value=f"{message.author.mention} (ID: {message.author.id})", inline=False)
            log_embed.add_field(name="Message", value=message.content, inline=False)
            log_embed.add_field(name="Reason", value=violation_reason, inline=False)
            if flagged_scores_dict:
                scores_str = "\n".join(f"**{cat}**: {score}" for cat, score in flagged_scores_dict.items())
                log_embed.add_field(name="Category Scores", value=scores_str, inline=False)
            log_embed.add_field(name="Previous Violations", value=current_violation_number, inline=False)
            log_embed.add_field(name="Time", value=violation_time, inline=False)
            log_embed.add_field(name="Message Link", value=msg_link, inline=False)
            if log_channel:
                try:
                    await log_channel.send(embed=log_embed)
                    Logger.info(f"Logged violation for message {message.id} in channel {log_channel_id}")
                except Exception as e:
                    Logger.error(f"Failed to send log embed to channel {log_channel_id}: {e}")
            else:
                Logger.error(f"Logging channel with ID {log_channel_id} not found.")

        # Create violation entry and update user's moderation file.
        violation_entry = {
            "original_message": message.content,
            "message_id": message.id,
            "reason": violation_reason,
            "category_scores": flagged_scores_dict,
            "time": datetime.datetime.utcnow().isoformat() + " UTC"
        }
        violations.append(violation_entry)
        try:
            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(violations, f, indent=4)
            Logger.debug(f"Updated moderation file for user {message.author.id}")
        except Exception as e:
            Logger.error(f"Error writing moderation file for user {message.author.id}: {e}")

        # If timeout is enabled, timeout the user.
        if self.mod_settings.get("timeout_enabled", False) and message.guild:
            timeout_str = self.mod_settings.get("timeout_duration", "1m")
            timeout_delta = parse_timeout(timeout_str)
            if timeout_delta:
                member = message.guild.get_member(message.author.id)
                if member:
                    try:
                        # Pass the timeout_delta as a positional argument.
                        await member.timeout(timeout_delta, reason="Content moderation violation")
                        Logger.info(f"Timed out user {message.author.id} for duration {timeout_delta}")
                    except Exception as e:
                        Logger.error(f"Failed to timeout user {message.author.id}: {e}")
                else:
                    Logger.error(f"Could not find member object for user {message.author.id} in the guild.")

        # Delete the original message if delete_original_message is true.
        if self.mod_settings.get("delete_original_message", False):
            try:
                await message.delete()
                Logger.info(f"Deleted message {message.id} due to moderation violation.")
            except Exception as e:
                Logger.error(f"Failed to delete message {message.id}: {e}")
        else:
            Logger.info(f"delete_original_message is disabled; not deleting message {message.id}.")

    async def setup(bot: commands.Bot):
        pass  # Not used

async def setup(bot: commands.Bot):
    cog = AutoModeration(bot)
    await bot.add_cog(cog)
    Logger.info("AutoModeration cog loaded from tasks/AutoModeration.py")