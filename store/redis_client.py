import json
import os
import uuid
from datetime import datetime, timezone

import redis

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)

LABELS = ["bug", "feature", "praise", "question", "other"]


def build_record(
    *,
    text,
    author,
    source,
    label,
    confidence,
    classifier,
    created_at=None,
    channel_id=None,
    message_id=None,
    jump_url=None,
    label_isolated=None,
    used_context=False,
    speaker_id=None,
    transcript_snippet=None,
):
    return {
        "id": str(uuid.uuid4()),
        "source": source,
        "text": text,
        "author": author,
        "channel_id": channel_id,
        "message_id": message_id,
        "jump_url": jump_url,
        "label": label,
        "confidence": confidence,
        "classifier": classifier,
        "label_isolated": label_isolated,
        "used_context": used_context,
        "speaker_id": speaker_id,
        "transcript_snippet": transcript_snippet,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


def save_feedback(item):
    data = json.dumps(item)
    label = item.get("label") or item.get("category")
    pipe = r.pipeline()
    pipe.lpush("feedback:all", data)
    pipe.lpush(f"feedback:{label}", data)
    pipe.incr("stats:processed")
    pipe.execute()


def get_recent(limit=50):
    items = r.lrange("feedback:all", 0, limit - 1)
    return [json.loads(i) for i in items]


def get_by_category(category, limit=50):
    items = r.lrange(f"feedback:{category}", 0, limit - 1)
    return [json.loads(i) for i in items]


def get_stats():
    return {c: r.llen(f"feedback:{c}") for c in LABELS}


def get_processed():
    return int(r.get("stats:processed") or 0)
