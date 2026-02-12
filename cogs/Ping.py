import discord
from discord.ext import commands
from discord import app_commands
from helpers.Logger import Logger

class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Shows bot current latency in ms.")
    async def ping(self, interaction: discord.Interaction):
        bot_latency = round(self.bot.latency * 1000)
        response = f"Ping command used; latency: {bot_latency} ms"
        Logger.info(response)
        
        # Log the command execution details via Logger.LogDiscord
        await Logger.LogDiscord(
            self.bot,
            command="ping",
            user=str(interaction.user)
        )

        await interaction.response.send_message(response, ephemeral=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))