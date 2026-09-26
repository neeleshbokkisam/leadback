import asyncio
import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from dotenv import load_dotenv

from bot.nlp import categorize
from bot.integrations import forward_feedback
from bot.stt import MAX_AUDIO_BYTES, STTError, get_stt, is_audio_filename
from store.redis_client import save_feedback

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("leadback")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID", 0))
DISCORD_PREVIEW = 1800


@client.event
async def on_ready():
    log.info("connected as %s, watching channel %s", client.user, CHANNEL_ID)


async def _reply(message, text):
    try:
        await message.reply(text, mention_author=False)
    except (discord.Forbidden, discord.HTTPException):
        log.info("discord reply failed")


async def _handle_audio(message, attachments):
    stt = get_stt()
    for att in attachments:
        if att.size and att.size > MAX_AUDIO_BYTES:
            await _reply(message, "file too large: %s" % att.filename)
            continue
        try:
            audio = await att.read()
            transcript = await asyncio.to_thread(stt.transcribe, audio, att.filename)
        except STTError as e:
            log.info("stt.fail discord file=%s err=%s", att.filename, e)
            await _reply(message, "transcription failed: %s" % e)
            continue
        except (discord.HTTPException, discord.NotFound) as e:
            log.info("stt.fail discord download file=%s err=%s", att.filename, e)
            await _reply(message, "could not download %s" % att.filename)
            continue

        text = (transcript.text or "").strip() or "(empty transcript)"
        if len(text) > DISCORD_PREVIEW:
            text = text[:DISCORD_PREVIEW] + "…"
        await _reply(message, "transcript (%s):\n%s" % (att.filename, text))


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id != CHANNEL_ID:
        return

    audio_atts = [a for a in message.attachments if is_audio_filename(a.filename)]
    if audio_atts:
        await _handle_audio(message, audio_atts)
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
