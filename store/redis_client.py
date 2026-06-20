import os
import json
import redis

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)


def save_feedback(item):
    data = json.dumps(item)
    r.lpush("feedback:all", data)
    r.lpush(f"feedback:{item['category']}", data)


def get_recent(limit=50):
    items = r.lrange("feedback:all", 0, limit - 1)
    return [json.loads(i) for i in items]


def get_by_category(category, limit=50):
    items = r.lrange(f"feedback:{category}", 0, limit - 1)
    return [json.loads(i) for i in items]


def get_stats():
    categories = ["bug", "feature", "praise", "question", "other"]
    return {c: r.llen(f"feedback:{c}") for c in categories}
