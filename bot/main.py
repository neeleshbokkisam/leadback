import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from dotenv import load_dotenv

from bot.nlp import categorize
from bot.integrations import forward_feedback
from store.redis_client import save_feedback

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("leadback")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID", 0))


@client.event
async def on_ready():
    log.info("connected as %s, watching channel %s", client.user, CHANNEL_ID)


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id != CHANNEL_ID:
        return

    item = categorize(message.content, str(message.author))
    save_feedback(item)
    forward_feedback(item)
    log.info("saved %s from %s", item["category"], item["author"])

    try:
        await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
    except (discord.Forbidden, discord.HTTPException):
        await message.reply(item["category"], mention_author=False)


if __name__ == "__main__":
    client.run(os.getenv("DISCORD_TOKEN"))
