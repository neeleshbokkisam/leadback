import spacy
from datetime import datetime, timezone

nlp = spacy.load("en_core_web_sm")

BUG_WORDS = {"bug", "broken", "crash", "error", "fix", "issue"}
FEATURE_WORDS = {"want", "add", "feature", "request", "need", "would"}
PRAISE_WORDS = {"love", "great", "thanks", "awesome", "amazing", "good"}
QUESTION_STARTS = {"how", "what", "why", "when", "where", "can", "is", "do"}


def categorize(text, author):
    lowered = text.lower()
    first = lowered.split()[0] if lowered.split() else ""

    category = "other"
    if any(w in lowered for w in BUG_WORDS) or "doesn't work" in lowered or "not working" in lowered:
        category = "bug"
    elif any(w in lowered for w in FEATURE_WORDS):
        category = "feature"
    elif any(w in lowered for w in PRAISE_WORDS):
        category = "praise"
    elif text.strip().endswith("?") or first in QUESTION_STARTS:
        category = "question"

    return {
        "text": text,
        "author": author,
        "category": category,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
