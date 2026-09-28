import logging
import os

from bot.nlp import classify_rules

log = logging.getLogger("leadback")

LABELS = ("bug", "feature", "praise", "question", "other")

TOOL = {
    "name": "label_feedback",
    "description": "Assign one feedback label.",
    "input_schema": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": list(LABELS)},
            "confidence": {"type": "number"},
            "rationale": {"type": "string"},
        },
        "required": ["label", "confidence", "rationale"],
    },
}

EXAMPLES = """
Message: the export button crashes when I click it
{"label":"bug","confidence":0.95,"rationale":"crash on click"}

Message: please add csv export
{"label":"feature","confidence":0.9,"rationale":"asks for something new"}

Message: love the new dashboard
{"label":"praise","confidence":0.92,"rationale":"positive reaction"}
""".strip()


def rules_result(text):
    return {
        "label": classify_rules(text),
        "confidence": 0.5,
        "rationale": "rules",
        "classifier": "rules",
    }


def llm_classify(text, context_messages=None):
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "")
    if not api_key or not model:
        return rules_result(text)

    timeout = float(os.getenv("CLASSIFIER_TIMEOUT", "20"))
    context = ""
    if context_messages:
        lines = "\n".join(f"- {line}" for line in context_messages if line)
        context = f"\nContext:\n{lines}\n"

    prompt = (
        "Label one piece of product feedback as bug, feature, praise, question, or other.\n"
        "Use the tool. confidence is between 0 and 1.\n"
        "If context is present, use it to resolve an ambiguous line. Label only the message.\n\n"
        f"Examples:\n{EXAMPLES}\n"
        f"{context}\nMessage: {text}"
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        resp = client.messages.create(
            model=model,
            max_tokens=256,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "label_feedback"},
            messages=[{"role": "user", "content": prompt}],
            extra_body={"temperature": 0},
        )
    except Exception as e:  # noqa: BLE001  provider errors fall back to rules
        log.info("llm classify failed: %s", e)
        return rules_result(text)

    data = None
    for block in resp.content:
        if (
            getattr(block, "type", None) == "tool_use"
            and block.name == "label_feedback"
        ):
            data = block.input
            break
    if not isinstance(data, dict):
        return rules_result(text)

    label = data.get("label")
    if label not in LABELS:
        return rules_result(text)
    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        return rules_result(text)
    confidence = min(1.0, max(0.0, confidence))
    rationale = str(data.get("rationale") or "")
    return {
        "label": label,
        "confidence": confidence,
        "rationale": rationale,
        "classifier": "llm",
    }
