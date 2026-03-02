import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path
import asyncio
import datetime
from helpers.Logger import Logger

class Tips(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Load settings from settings.json.
        settings_path = Path("./settings.json")
        with open(settings_path, "r", encoding="utf-8") as f:
            self.settings = json.load(f)
        # Define path to tips data file.
        self.tips_file = Path("./data/tips.json")
        if not self.tips_file.exists():
            with open(self.tips_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4)

    @app_commands.command(
        name="tip-add",
        description="Add a tip from a message ID."
    )
    async def tip_add(self, interaction: discord.Interaction, id: str):
        # Parse the input message id.
        try:
            original_message_id = int(id)
        except Exception:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return

        # Retrieve the original message from the channel where the slash command was used.
        try:
            original_message = await interaction.channel.fetch_message(original_message_id)
        except Exception as e:
            Logger.error(f"Failed to fetch message {original_message_id}: {e}")
            await interaction.response.send_message("Could not retrieve the message.", ephemeral=True)
            return

        # Create an embed from the original message content.
        embed = discord.Embed(
            title="New Tip",
            description=original_message.content,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )

        # Choose the tip voting channel from settings (development/production).
        env = self.settings["bot"]["environment"]
        if env == "development":
            voting_channel_id = self.settings["tips"]["development"]["tip_voting_channel"]
        else:
            voting_channel_id = self.settings["tips"]["production"]["tip_voting_channel"]

        tip_voting_channel = self.bot.get_channel(voting_channel_id)
        if tip_voting_channel is None:
            await interaction.response.send_message("Tip voting channel not found.", ephemeral=True)
            return

        # Post the embed in the tip voting channel.
        try:
            tip_vote_message = await tip_voting_channel.send(embed=embed)
        except Exception as e:
            Logger.error(f"Failed to send tip embed: {e}")
            await interaction.response.send_message("Failed to post tip.", ephemeral=True)
            return

        # Save the tip with the key as the new tip vote message ID.
        try:
            with open(self.tips_file, "r", encoding="utf-8") as f:
                tips_data = json.load(f)
        except Exception as e:
            Logger.error(f"Failed to load tips data: {e}")
            tips_data = {}
        tips_data[str(tip_vote_message.id)] = {
            "original_message_id": original_message_id,
            "content": original_message.content,
            "upvotes": 0,
            "downvotes": 0,
            "approved": False  # Marker to indicate if the tip has been approved.
        }
        try:
            with open(self.tips_file, "w", encoding="utf-8") as f:
                json.dump(tips_data, f, indent=4)
        except Exception as e:
            Logger.error(f"Failed to save tip data: {e}")
            await interaction.response.send_message("Failed to save tip.", ephemeral=True)
            return

        Logger.info(f"Tip saved for tip message {tip_vote_message.id} (original message {original_message_id})")

        # Add thumbs up and thumbs down reactions.
        try:
            await tip_vote_message.add_reaction("👍")
            await tip_vote_message.add_reaction("👎")
        except Exception as e:
            Logger.error(f"Failed to add reactions to tip message {tip_vote_message.id}: {e}")

        await interaction.response.send_message("Tip added successfully!", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ignore if the reaction was made by the bot.
        if payload.user_id == self.bot.user.id:
            return

        try:
            with open(self.tips_file, "r", encoding="utf-8") as f:
                tips_data = json.load(f)
        except Exception as e:
            Logger.error(f"Error reading tips data: {e}")
            return

        tip_entry = tips_data.get(str(payload.message_id))
        if tip_entry is None:
            return  # Not a tracked tip message.

        emoji = str(payload.emoji)
        if emoji == "👍":
            tip_entry["upvotes"] += 1
            Logger.info(f"Incremented upvotes for tip {payload.message_id}: now {tip_entry['upvotes']}")
        elif emoji == "👎":
            tip_entry["downvotes"] += 1
            Logger.info(f"Incremented downvotes for tip {payload.message_id}: now {tip_entry['downvotes']}")
        else:
            return  # Ignore other emojis.

        try:
            with open(self.tips_file, "w", encoding="utf-8") as f:
                json.dump(tips_data, f, indent=4)
        except Exception as e:
            Logger.error(f"Error saving updated tips data: {e}")

        # Check if the tip is not already approved and if upvotes meet the minimum threshold.
        if not tip_entry.get("approved", False):
            min_votes = self.settings["tips"].get("min_votes", 5)
            if tip_entry["upvotes"] >= min_votes:
                env = self.settings["bot"]["environment"]
                if env == "development":
                    tips_channel_id = self.settings["tips"]["development"]["tips_channel"]
                else:
                    tips_channel_id = self.settings["tips"]["production"]["tips_channel"]
                tips_channel = self.bot.get_channel(tips_channel_id)
                if tips_channel is None:
                    Logger.error("Approved tips channel not found!")
                    return
                # Repost the tip embed (without reactions).
                embed = discord.Embed(
                    title="Approved Tip",
                    description=tip_entry["content"],
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )
                try:
                    approved_message = await tips_channel.send(embed=embed)
                    Logger.info(f"Tip {payload.message_id} approved and posted in tips channel: {approved_message.id}")
                    tip_entry["approved"] = True  # Mark tip as approved.
                    with open(self.tips_file, "w", encoding="utf-8") as f:
                        json.dump(tips_data, f, indent=4)
                except Exception as e:
                    Logger.error(f"Failed to post approved tip: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        try:
            with open(self.tips_file, "r", encoding="utf-8") as f:
                tips_data = json.load(f)
        except Exception as e:
            Logger.error(f"Error reading tips data on reaction remove: {e}")
            return

        tip_entry = tips_data.get(str(payload.message_id))
        if tip_entry is None:
            return  # Not a tracked tip.

        emoji = str(payload.emoji)
        if emoji == "👍":
            tip_entry["upvotes"] = max(0, tip_entry["upvotes"] - 1)
            Logger.info(f"Decremented upvotes for tip {payload.message_id}: now {tip_entry['upvotes']}")
        elif emoji == "👎":
            tip_entry["downvotes"] = max(0, tip_entry["downvotes"] - 1)
            Logger.info(f"Decremented downvotes for tip {payload.message_id}: now {tip_entry['downvotes']}")
        else:
            return

        try:
            with open(self.tips_file, "w", encoding="utf-8") as f:
                json.dump(tips_data, f, indent=4)
        except Exception as e:
            Logger.error(f"Error saving updated tips data on reaction remove: {e}")

async def setup(bot: commands.Bot):
    cog = Tips(bot)
    await bot.add_cog(cog)
    Logger.info("Tips cog loaded from cogs/Tips.py")