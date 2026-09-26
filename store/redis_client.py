import os
import json
import redis

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)

LABELS = ["bug", "feature", "praise", "question", "other"]


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
