import asyncio
import logging
import os

import requests

log = logging.getLogger("leadback")


def _label(item):
    return item.get("label") or item.get("category")


def _to_notion(item):
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DATABASE_ID")
    if not token or not db_id:
        return
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "parent": {"database_id": db_id},
            "properties": {
                "Name": {"title": [{"text": {"content": item["text"][:100]}}]},
                "Category": {"select": {"name": _label(item)}},
            },
        },
        timeout=10,
    )
    if resp.status_code >= 400:
        log.info("notion forward failed: %s %s", resp.status_code, resp.text[:200])


def _to_slack(item):
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        return
    label = _label(item)
    resp = requests.post(
        url,
        json={"text": f"[{label}] {item['author']}: {item['text']}"},
        timeout=10,
    )
    if resp.status_code >= 400:
        log.info("slack forward failed: %s %s", resp.status_code, resp.text[:200])


async def forward_feedback(item):
    try:
        await asyncio.to_thread(_to_notion, item)
    except Exception as e:
        log.info("notion forward failed: %s", e)
    try:
        await asyncio.to_thread(_to_slack, item)
    except Exception as e:
        log.info("slack forward failed: %s", e)
