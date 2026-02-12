Ensure that only one call to `Logger.LogDiscord()` method is only called once per command
All command descriptions should be 100 characters or less to avoid any errors with discord.py
Ensure that all code contains console logs are extremely detailed and concise
Never truncate any code
Always give code inside of codeblocks
Never give snippets of code
Always give the entire full code of the file that the user is currently working on without any truncations or snippets of code. Never leave any code out, all code should be able to be copy and pasted into the users code editor and run without any errors.
ensure that all code given is accurate, and will work 100% of the time. Failure, errors, and warnings will not be tolerated.
Always give a bulleted list summary at the end of your response of what we have added, changed, or deleted
The bot token is located at `.\auth\.bot_token`
The OpenAI API key is located at `.\auth\.openai_api_key`
General bot settings are located at `.\settings.json` and will be a simple key value pair object. Example: `{"key": "value", "key": "value"}`
All slash commands will be located in `.\cogs`
All helper functions will be located at `.\helpers`
All data the bot will use or manipulate will be located within `.\data`
The players data file is located at `.\data\Players\<DISCORD-ID>.json`
All custom python exceptions will be located at `.\exceptions`
All automated / timed tasks will be located in `.\tasks`
All temporary files will be located at `.\data\temp`
The bots main file is located at `.\bot.py`
Never output errors to users, but always output errors to console
All logs or logfiles will be located within `.\logs` and will use the `Logger.py` helper file located at `.\helpers\Logger.py` and never should use the `print()` method. The `Logger.py` file should be the exclusive way to write logs to console and the logfile itself
When importing the `Logger.py` file you should always use `from helpers.Logger import Logger`
All commands, cogs, and tasks will be wrapped inside of an `asyncio.to_thread()` method to avoid a heartbeat exception due to connectivity issues.
Always ensure that all imports are located at the top of the file and never inside any functions within the file.
All commands / cogs should be logged to discord using the `LogDiscord()` function located in the `.\helpers\Logger.py` file. The function and docblock is below:
```python
async def LogDiscord(cls, bot, command: str, user: str):
    """
    Logs command details to the Discord logs channel using an embed.
    
    Parameters:
        bot: The running Discord bot/client instance.
        command: The command being executed.
        user: The user who executed the command.
    """
```
Example Usage:
```python
    # Log the command execution details via Logger.LogDiscord
    await Logger.LogDiscord(
        self.bot,
        command="ping",
        user=str(interaction.user)
    )
```
Never use discord context. Always use discord interactions instead in all slash commands.
Always use discord.app_commands.command for slash commands and ensure that the setup function is asynchronous (async def setup(bot: commands.Bot): await bot.add_cog(...)) to maintain compatibility with the latest discord.py version.