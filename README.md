# leadback

Discord feedback comes in as text or a voice note. I transcribe voice, label each item with an LLM classifier, store it in Redis, and show it on a local dashboard. The same item can be forwarded to Slack and Notion.

## Demo

TODO: record docs/demo.gif

TODO: screenshot docs/dashboard.png

## How it works

```
discord text, voice, or thread
        |
        v
transcribe voice (wav, mp3, m4a, ogg)
        |
        v
llm classifier ---- if the key or model is unset, or the call fails --> rules
        |
        v
context retry
  thread or reply: always
  top-level: only if confidence < 0.7 or label is other
        |
        v
redis --> dashboard
      --> slack
      --> notion
```

## Classification

Rules baseline, from `classify_rules`:

| message | label |
| --- | --- |
| there is a bug in export | bug |
| please add csv export | feature |
| love the new dashboard | praise |

Context retry, from `python scripts/export_before_after.py`:

TODO: no rows in eval/context_retries.jsonl yet

Text eval, from `python eval/text_eval.py`:

TODO: paste eval/results_text.md here after the example rows in eval/labeled.jsonl are replaced

## Voice

TODO: paste eval/results_voice.md here after clips are listed in eval/voice/manifest.jsonl

## Record

```
{
  "id": "uuid",
  "source": "discord_text | discord_voice | api_audio | replay",
  "text": "",
  "author": "",
  "channel_id": "",
  "message_id": "",
  "jump_url": "",
  "label": "bug | feature | praise | question | other",
  "confidence": 0.0,
  "classifier": "llm | llm+context | rules",
  "label_isolated": null,
  "used_context": false,
  "speaker_id": null,
  "transcript_snippet": null,
  "created_at": "UTC ISO"
}
```

`confidence` in that block is the field type, not a measured score. `jump_url` is null when the item did not come from Discord.

## Integrations

TODO: screenshot docs/slack.png

TODO: screenshot docs/discord.png

TODO: screenshot docs/notion.png

## Run it locally

```bash
pip install -r requirements.txt
docker compose up -d
cp .env.example .env
python bot/main.py
python api/app.py
```

Dashboard: http://localhost:5000

In the Discord developer portal, turn on the Message Content intent. The bot needs Read Message History, Send Messages, Add Reactions, and Create Public Threads.

| variable | required |
| --- | --- |
| DISCORD_TOKEN | yes |
| FEEDBACK_CHANNEL_ID | yes |
| REDIS_URL | defaults to redis://localhost:6379 |
| LLM_API_KEY | no, rules baseline if blank |
| LLM_MODEL | no, rules baseline if blank |
| CLASSIFIER_TIMEOUT | no, default 20 seconds |
| CONTEXT_THRESHOLD | no, default 0.7 |
| ELEVENLABS_API_KEY | voice only |
| ELEVENLABS_TIMEOUT | no |
| STT_PROVIDER | no, default elevenlabs |
| NOTION_TOKEN | no |
| NOTION_DATABASE_ID | no |
| SLACK_WEBHOOK_URL | no |
| DEMO_WEBHOOK_URL | only for scripts/demo_post.py |

Put the model id in `.env`. `.env.example` leaves `LLM_MODEL` blank on purpose.

`scripts/replay.py` reads a CSV or JSONL I supply (`text`, `author`, `created_at`). It does not invent messages.

## Limitations

One feedback channel, plus threads under that channel. The dashboard has no auth. I run it on localhost. The labeled eval set is still the example rows, so there is no accuracy number yet.
