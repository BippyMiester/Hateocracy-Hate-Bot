import discord
from discord.ext import commands
import asyncio
import json
from pathlib import Path
import openai
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from helpers.Logger import Logger
import re

class AITask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def pong(self, message: discord.Message):
        Logger.debug(f"Executing pong in AITask for user {message.author} in channel {message.channel.id}")
        # Load settings to retrieve OpenAI configuration.
        settings_path = Path("./settings.json")
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings_data = json.load(f)
            ai_settings = settings_data["ai"]
            currently_processing = ai_settings["currently_processing"]
        except Exception as e:
            Logger.error(f"Error loading settings.json in AITask: {e}")
            await message.channel.send("Something went wrong. Error Code: AITASK001")
            return

        # If an API request is already running, skip processing.
        if currently_processing is True:
            Logger.info("Currently processing OpenAI API request, skipping AITask Pong message.")
            return

        try:
            openai_api_key = ai_settings["openai_api_key"]
            model = ai_settings["model"]
            max_input_tokens = ai_settings["max_input_tokens"]
            max_completion_tokens = ai_settings["max_completion_tokens"]
            previous_message_count = ai_settings["previous_messages"]
        except KeyError as ke:
            Logger.error(f"Missing required AI setting: {ke}")
            await message.channel.send("Something went wrong. Error Code: AITASK003")
            return

        # Load the system prompt from the markdown file.
        system_prompt_path = Path("./openai/context.md")
        try:
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read().strip()
            if not system_prompt:
                raise Exception("System prompt file is empty.")
        except Exception as e:
            Logger.error(f"Error loading system prompt from {system_prompt_path}: {e}")
            await message.channel.send("Something went wrong. Error Code: AITASK004")
            return

        # Helper function to remove stop words (keeping numbers and punctuation intact).
        def remove_stopwords(text: str) -> str:
            tokens = word_tokenize(text.lower())
            custom_stop_words = set(stopwords.words('english') + ["uh", "um", "yeah", "like"])
            filtered_tokens = [word for word in tokens if word not in custom_stop_words]
            return ' '.join(filtered_tokens)

        # Construct the JSON payload:
        # Original message is the current message that bot is replying to
        # Previous messages are fetched from the channel history (sorted in ascending order)
        original_message = {
            "user": message.author.id,
            "message": remove_stopwords(message.content)
        }
        previous_messages = []
        try:
            # Fetch previous messages from the channel history (excluding the current one)
            history = []
            async for msg in message.channel.history(limit=previous_message_count, before=message):
                history.append(msg)
            # Reverse to have the oldest messages first.
            history = list(reversed(history))
            for msg in history:
                previous_messages.append({
                    "user": msg.author.id,
                    "message": remove_stopwords(msg.content)
                })
        except Exception as e:
            Logger.error(f"Error fetching previous messages: {e}")
            # Continue with an empty previous_messages list if history fails
        
        # Construct the JSON structure
        user_payload = {
            "original_message": original_message,
            "previous_messages": previous_messages
        }
        # Convert the payload to a JSON string.
        user_text = json.dumps(user_payload, indent=4)
        Logger.info(f"Constructed user_text payload for OpenAI API:\n{user_text}")

        # Helper function to update only the "currently_processing" value in settings.json.
        def update_currently_processing(value: bool):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings_local = json.load(f)
                settings_local["ai"]["currently_processing"] = value
                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(settings_local, f, indent=4)
                Logger.info(f"Set currently_processing to {value} in settings.json")
            except Exception as e:
                Logger.error(f"Error updating settings.json: {e}")

        # Define an internal asynchronous function to call OpenAI.
        async def call_openai(system_prompt: str, user_text: str, max_tokens: int) -> str:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=openai_api_key)
            # Check token count and truncate if necessary.
            tokens = word_tokenize(user_text)
            if len(tokens) > max_input_tokens:
                Logger.warning(f"Truncating user input from {len(tokens)} tokens to {max_input_tokens} tokens.")
                tokens = tokens[:max_input_tokens]
                user_text = ' '.join(tokens)
            Logger.info(f"Final user text token count: {len(word_tokenize(user_text))} tokens.")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
            
            async def run_api():
                # Set currently_processing to true before the API call.
                update_currently_processing(True)
                try:
                    # Await the asynchronous OpenAI API call.
                    completion = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=1,
                        max_completion_tokens=max_tokens
                    )
                    Logger.debug(f"Raw OpenAI response: {completion.model_dump()}")
                    finish_reason = completion.choices[0].finish_reason
                    Logger.info(f"OpenAI finish_reason: {finish_reason}")
                    result = completion.choices[0].message.content.strip()
                    return result
                finally:
                    # Set currently_processing to false after the API call completes.
                    update_currently_processing(False)
            
            # Wrap the asynchronous run_api call to keep the heartbeat alive.
            result = await asyncio.to_thread(lambda: asyncio.run(run_api()))
            Logger.info(f"OpenAI returned a response of length {len(result)}")
            if not result or result.isspace():
                Logger.error("OpenAI returned an empty response.")
                raise Exception("Empty response from OpenAI")
            return result

        # Call the OpenAI API with the constructed JSON payload.
        try:
            Logger.debug(f"Calling OpenAI API for user {message.author} with payload.")
            openai_reply = await call_openai(system_prompt, user_text, max_completion_tokens)
            await message.channel.send(openai_reply)
            Logger.info(f"Replied with AI response to user {message.author} in channel {message.channel.id}")
        except Exception as e:
            Logger.error(f"Error in OpenAI API call: {e}")
            await message.channel.send("Something went wrong. Error Code: AITASK002")

async def setup(bot: commands.Bot):
    cog = AITask(bot)
    await bot.add_cog(cog)
    Logger.info("AITask cog loaded from tasks/ai.py")