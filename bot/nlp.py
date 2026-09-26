import re

BUG_WORDS = {"bug", "broken", "crash", "error", "fix", "issue"}
FEATURE_WORDS = {"want", "add", "feature", "request", "need", "would"}
PRAISE_WORDS = {"love", "great", "thanks", "awesome", "amazing", "good"}
QUESTION_STARTS = {"how", "what", "why", "when", "where", "can", "is", "do"}
BUG_PHRASES = ("doesn't work", "not working")


def _has_term(text, term):
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def classify_rules(text):
    lowered = text.lower()
    first = lowered.split()[0] if lowered.split() else ""

    if any(_has_term(lowered, w) for w in BUG_WORDS) or any(
        _has_term(lowered, p) for p in BUG_PHRASES
    ):
        return "bug"
    if any(_has_term(lowered, w) for w in FEATURE_WORDS):
        return "feature"
    if any(_has_term(lowered, w) for w in PRAISE_WORDS):
        return "praise"
    if text.strip().endswith("?") or first in QUESTION_STARTS:
        return "question"
    return "other"
