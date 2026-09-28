import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# webhooks cannot set message_reference, so the ambiguous line goes in a thread
LINES = [
    ("Ava", "the export button crashes when I click it"),
    ("Ben", "please add a csv export"),
    ("Chen", "love the new dashboard"),
    ("Dia", "how do I reset my password?"),
    ("Eli", "search returns the wrong project"),
    ("Fran", "thanks, billing is much clearer now"),
    ("Gus", "app crashes every time I upload a photo on iOS"),
]
THREAD_LINE = ("Hana", "same on my phone")
PAUSE = 2.5


def post_webhook(url, content, username, thread_id=None):
    params = {"wait": "true"}
    if thread_id:
        params["thread_id"] = str(thread_id)
    resp = requests.post(
        url,
        params=params,
        json={"content": content, "username": username},
        timeout=20,
    )
    if resp.status_code >= 400:
        print(f"webhook failed: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def open_thread(channel_id, message_id, token):
    resp = requests.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/threads",
        headers={"Authorization": f"Bot {token}"},
        json={"name": "mobile", "auto_archive_duration": 1440},
        timeout=20,
    )
    if resp.status_code >= 400:
        print(
            f"thread create failed: {resp.status_code} {resp.text[:200]}",
            file=sys.stderr,
        )
        print("the bot needs Create Public Threads", file=sys.stderr)
        sys.exit(1)
    return resp.json()["id"]


def main():
    url = os.getenv("DEMO_WEBHOOK_URL", "")
    token = os.getenv("DISCORD_TOKEN", "")
    channel_id = os.getenv("FEEDBACK_CHANNEL_ID", "")
    if not url or not token or not channel_id:
        print(
            "set DEMO_WEBHOOK_URL, DISCORD_TOKEN, and FEEDBACK_CHANNEL_ID",
            file=sys.stderr,
        )
        sys.exit(1)

    parent = None
    for username, content in LINES:
        parent = post_webhook(url, content, username)
        print(f"posted {username}")
        time.sleep(PAUSE)

    thread_id = open_thread(channel_id, parent["id"], token)
    username, content = THREAD_LINE
    post_webhook(url, content, username, thread_id=thread_id)
    print(f"posted {username} in thread {thread_id}")


if __name__ == "__main__":
    main()
