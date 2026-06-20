import os
import requests


def forward_feedback(item):
    _to_notion(item)
    _to_slack(item)


def _to_notion(item):
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DATABASE_ID")
    if not token or not db_id:
        return
    requests.post(
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
                "Category": {"select": {"name": item["category"]}},
            },
        },
        timeout=10,
    )


def _to_slack(item):
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        return
    requests.post(
        url,
        json={"text": f"[{item['category']}] {item['author']}: {item['text']}"},
        timeout=10,
    )
