import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from bot.classify import llm_classify
from store.redis_client import LABELS, build_record, save_feedback

load_dotenv(ROOT / ".env")

PROGRESS = ROOT / "eval" / "replay_progress.json"
SUMMARY = ROOT / "eval" / "replay_summary.json"


def load_rows(path):
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                yield row
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            yield json.loads(line)


def read_progress():
    if not PROGRESS.exists():
        return {}
    return json.loads(PROGRESS.read_text(encoding="utf-8"))


def write_progress(data):
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(data), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="classify a message export into redis")
    parser.add_argument("path", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    path = args.path.expanduser().resolve()
    if not path.is_file():
        print("missing file: %s" % path, file=sys.stderr)
        sys.exit(1)

    key = str(path)
    progress = read_progress()
    if args.reset:
        progress.pop(key, None)
    done = int(progress.get(key, 0))

    counts = {label: 0 for label in LABELS}
    saved = 0
    index = 0
    for row in load_rows(path):
        if index < done:
            index += 1
            continue
        if args.limit and saved >= args.limit:
            break
        text = (row.get("text") or "").strip()
        if not text:
            index += 1
            continue
        result = llm_classify(text)
        item = build_record(
            text=text,
            author=(row.get("author") or "replay").strip() or "replay",
            source="replay",
            label=result["label"],
            confidence=result["confidence"],
            classifier=result["classifier"],
            created_at=row.get("created_at") or None,
        )
        save_feedback(item)
        counts[result["label"]] = counts.get(result["label"], 0) + 1
        saved += 1
        index += 1
        progress[key] = index
        write_progress(progress)
        if args.delay:
            time.sleep(args.delay)

    summary = {"count": saved, "labels": counts}
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
