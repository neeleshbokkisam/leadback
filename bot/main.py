import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from dotenv import load_dotenv

from bot.nlp import categorize
from store.redis_client import save_feedback

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID", 0))


@client.event
async def on_ready():
    print(f"connected as {client.user}")


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id != CHANNEL_ID:
        return

    item = categorize(message.content, str(message.author))
    save_feedback(item)
    await message.add_reaction("✓")


if __name__ == "__main__":
    client.run(os.getenv("DISCORD_TOKEN"))
