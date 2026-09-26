import asyncio
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from bot.classify import llm_classify
from bot.integrations import forward_feedback
from bot.stt import MAX_AUDIO_BYTES, STTError, first_speaker_id, get_stt, is_audio_filename
from store.redis_client import build_record, get_processed, get_recent, get_stats, save_feedback

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_AUDIO_BYTES

COLORS = {
    "bug": "#cc4444",
    "feature": "#4488aa",
    "praise": "#44aa88",
    "question": "#aa8844",
    "other": "#888888",
}


def tint(color):
    return f"{color}22"


@app.route("/api/feedback")
def feedback():
    return jsonify(get_recent())


@app.route("/api/stats")
def stats():
    return jsonify(get_stats())


@app.errorhandler(RequestEntityTooLarge)
def too_large(_e):
    return jsonify({"error": "file too large"}), 413


@app.route("/api/ingest/audio", methods=["POST"])
def ingest_audio():
    if "file" not in request.files:
        return jsonify({"error": "missing file"}), 400
    f = request.files["file"]
    filename = f.filename or ""
    if not is_audio_filename(filename):
        return jsonify({"error": "unsupported type, use wav/mp3/m4a/ogg"}), 400
    audio = f.read()
    if not audio:
        return jsonify({"error": "empty file"}), 400
    if len(audio) > MAX_AUDIO_BYTES:
        return jsonify({"error": "file too large"}), 413
    try:
        transcript = get_stt().transcribe(audio, filename)
    except STTError as e:
        return jsonify({"error": str(e)}), 502
    text = (transcript.text or "").strip()
    if not text:
        return jsonify({"error": "empty transcript"}), 502
    result = llm_classify(text)
    author = (request.form.get("author") or "api").strip() or "api"
    item = build_record(
        text=text,
        author=author,
        source="api_audio",
        label=result["label"],
        confidence=result["confidence"],
        classifier=result["classifier"],
        speaker_id=first_speaker_id(transcript),
        transcript_snippet=text[:200],
    )
    save_feedback(item)
    asyncio.run(forward_feedback(item))
    return jsonify(item)


@app.route("/")
def dashboard():
    s = get_stats()
    items = get_recent(30)
    total = get_processed()

    chips = ""
    for cat, count in s.items():
        color = COLORS.get(cat, "#888888")
        chips += f'<span class="chip" style="background:{tint(color)};color:{color}">{html.escape(cat)} {count}</span>'

    rows = ""
    for item in items:
        label = item.get("label") or item.get("category") or "other"
        color = COLORS.get(label, "#888888")
        time = html.escape(item["created_at"][:16].replace("T", " "))
        text = html.escape(item.get("text") or "")
        author = html.escape(item.get("author") or "")
        rows += f"""<div class="row">
            <span class="tag" style="background:{tint(color)};color:{color}">{html.escape(label)}</span>
            <div class="body">
                <p>{text}</p>
                <small>{author} · {time}</small>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>leadback</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f6f4; color: #1a1a1a; }}
header {{ padding: 48px 24px 32px; max-width: 720px; margin: 0 auto; }}
h1 {{ font-size: 22px; font-weight: 600; letter-spacing: -0.3px; }}
.sub {{ color: #666; font-size: 14px; margin-top: 4px; }}
.stats {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 20px; }}
.chip {{ font-size: 13px; padding: 4px 10px; border-radius: 6px; font-weight: 500; }}
main {{ max-width: 720px; margin: 0 auto; padding: 0 24px 48px; }}
.row {{ display: flex; gap: 12px; padding: 16px 0; border-bottom: 1px solid #e8e8e6; }}
.tag {{ font-size: 11px; padding: 3px 8px; border-radius: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; height: fit-content; margin-top: 2px; }}
.body p {{ font-size: 15px; line-height: 1.5; }}
.body small {{ color: #999; font-size: 12px; }}
.empty {{ color: #999; font-size: 14px; padding: 32px 0; }}
</style>
</head>
<body>
<header>
    <h1>leadback</h1>
    <p class="sub">{total} messages processed</p>
    <div class="stats">{chips}</div>
</header>
<main>
    {rows if rows else '<p class="empty">no feedback yet</p>'}
</main>
</body>
</html>"""


if __name__ == "__main__":
    app.run(port=5000)
