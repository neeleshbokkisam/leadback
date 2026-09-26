import asyncio
import json
import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from dotenv import load_dotenv

from bot.classify import llm_classify
from bot.nlp import classify_rules
from bot.integrations import forward_feedback
from bot.stt import MAX_AUDIO_BYTES, STTError, first_speaker_id, get_stt, is_audio_filename
from store.redis_client import build_record, save_feedback

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("leadback")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID", 0))
DISCORD_PREVIEW = 1800
ACCEPTED_TYPES = {discord.MessageType.default, discord.MessageType.reply}
RETRY_LOG = Path(__file__).resolve().parent.parent / "eval" / "context_retries.jsonl"
THREAD_HISTORY = 50


@client.event
async def on_ready():
    log.info("connected as %s, watching channel %s", client.user, CHANNEL_ID)


def _timeout():
    return float(os.getenv("CLASSIFIER_TIMEOUT", "20"))


def _rules(text):
    return {
        "label": classify_rules(text),
        "confidence": 0.5,
        "rationale": "rules",
        "classifier": "rules",
    }


async def classify_text(text, context_messages=None):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(llm_classify, text, context_messages),
            timeout=_timeout(),
        )
    except asyncio.TimeoutError:
        log.info("llm classify timeout")
        return _rules(text)


def in_scope(message):
    if message.channel.id == CHANNEL_ID:
        return True
    return getattr(message.channel, "parent_id", None) == CHANNEL_ID


def in_thread(message):
    return getattr(message.channel, "parent_id", None) == CHANNEL_ID


def wants_context(message, isolated):
    if in_thread(message) or message.type == discord.MessageType.reply:
        return True
    threshold = float(os.getenv("CONTEXT_THRESHOLD", "0.7"))
    return isolated["confidence"] < threshold or isolated["label"] == "other"


def append_retry(row):
    RETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RETRY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


async def _message_text(message):
    if message is None:
        return ""
    return (message.content or "").strip()


async def referenced_text(message):
    ref = message.reference
    if ref is None or not ref.message_id:
        return ""
    target = ref.resolved
    if target is None:
        try:
            target = await message.channel.fetch_message(ref.message_id)
        except (discord.NotFound, discord.HTTPException, discord.Forbidden):
            log.info("context fetch failed: referenced message")
            return ""
    return await _message_text(target)


async def thread_lines(message):
    thread = message.channel
    lines = []
    starter = thread.starter_message
    if starter is None:
        # thread.id is the starter message id in the parent channel
        try:
            parent = thread.parent or await client.fetch_channel(thread.parent_id)
            starter = await parent.fetch_message(thread.id)
        except (discord.NotFound, discord.HTTPException, discord.Forbidden):
            log.info("context fetch failed: thread starter")
            starter = None
    starter_text = await _message_text(starter)
    if starter_text:
        lines.append(starter_text)

    prior = []
    async for older in thread.history(limit=THREAD_HISTORY, before=message):
        if older.type not in ACCEPTED_TYPES:
            continue
        text = await _message_text(older)
        if text and text not in lines:
            prior.append(text)
    prior.reverse()
    lines.extend(prior)
    return lines


async def channel_lines(message):
    prior = []
    async for older in message.channel.history(limit=5, before=message):
        if older.type not in ACCEPTED_TYPES:
            continue
        text = await _message_text(older)
        if text:
            prior.append(text)
    prior.reverse()
    return prior


async def gather_context(message):
    lines = []
    if message.type == discord.MessageType.reply:
        ref = await referenced_text(message)
        if ref:
            lines.append(ref)
        if not in_thread(message):
            return lines
    if in_thread(message):
        for line in await thread_lines(message):
            if line not in lines:
                lines.append(line)
        return lines
    return await channel_lines(message)


async def triage(text, message, source, speaker_id=None, transcript_snippet=None):
    isolated = await classify_text(text)
    final = isolated
    label_isolated = None
    used_context = False
    classifier = isolated["classifier"]

    if wants_context(message, isolated):
        context = await gather_context(message)
        second = await classify_text(text, context or None)
        if second["classifier"] == "llm":
            label_isolated = isolated["label"]
            final = second
            used_context = True
            classifier = "llm+context"
            append_retry(
                {
                    "text": text,
                    "context": context,
                    "label_isolated": label_isolated,
                    "label_context": second["label"],
                }
            )

    item = build_record(
        text=text,
        author=str(message.author),
        source=source,
        label=final["label"],
        confidence=final["confidence"],
        classifier=classifier,
        channel_id=str(message.channel.id),
        message_id=str(message.id),
        jump_url=message.jump_url,
        label_isolated=label_isolated,
        used_context=used_context,
        speaker_id=speaker_id,
        transcript_snippet=transcript_snippet,
    )
    save_feedback(item)
    await forward_feedback(item)
    log.info("saved %s from %s", item["label"], item["author"])
    return item


async def _reply(message, text):
    try:
        await message.reply(text, mention_author=False)
    except (discord.Forbidden, discord.HTTPException):
        log.info("discord reply failed")


async def _handle_audio(message, attachments):
    stt = get_stt()
    saved = None
    for att in attachments:
        if att.size and att.size > MAX_AUDIO_BYTES:
            await _reply(message, "file too large: %s" % att.filename)
            continue
        try:
            audio = await att.read()
            transcript = await asyncio.to_thread(stt.transcribe, audio, att.filename)
        except STTError as e:
            log.info("stt failed %s: %s", att.filename, e)
            await _reply(message, "transcription failed: %s" % e)
            continue
        except (discord.HTTPException, discord.NotFound) as e:
            log.info("stt download failed %s: %s", att.filename, e)
            await _reply(message, "could not download %s" % att.filename)
            continue

        text = (transcript.text or "").strip()
        if not text:
            await _reply(message, "transcript (%s): (empty transcript)" % att.filename)
            continue
        item = await triage(
            text,
            message,
            "discord_voice",
            speaker_id=first_speaker_id(transcript),
            transcript_snippet=text[:200],
        )
        saved = item
        preview = text if len(text) <= DISCORD_PREVIEW else text[:DISCORD_PREVIEW] + "…"
        await _reply(message, "transcript (%s):\n%s\nlabel: %s" % (att.filename, preview, item["label"]))

    written = (message.content or "").strip()
    if written:
        saved = await triage(written, message, "discord_text")
    if saved:
        await mark_saved(message, saved["label"])


async def mark_saved(message, label):
    try:
        await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
    except (discord.Forbidden, discord.HTTPException):
        await message.reply(label, mention_author=False)


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if not in_scope(message):
        return
    if message.type not in ACCEPTED_TYPES:
        return

    audio_atts = [a for a in message.attachments if is_audio_filename(a.filename)]
    if audio_atts:
        await _handle_audio(message, audio_atts)
        return

    item = await triage(message.content, message, "discord_text")
    await mark_saved(message, item["label"])


if __name__ == "__main__":
    client.run(os.getenv("DISCORD_TOKEN"))
