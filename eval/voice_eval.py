import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from bot.classify import llm_classify
from bot.stt import STTError, get_stt
from store.redis_client import LABELS

load_dotenv(ROOT / ".env")

MANIFEST = ROOT / "eval" / "voice" / "manifest.jsonl"
OUT = ROOT / "eval" / "results_voice.md"


def load_rows():
    if not MANIFEST.is_file():
        return []
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def normalize(text):
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def word_error_rate(reference, hypothesis):
    import jiwer

    ref = normalize(reference)
    hyp = normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return jiwer.wer(ref, hyp)


def main():
    rows = load_rows()
    if not rows:
        print("no clips in manifest", file=sys.stderr)
        sys.exit(1)

    stt = get_stt()
    wers = []
    true_hits = 0
    asr_hits = 0
    flips = []
    for row in rows:
        audio_path = Path(row["audio_path"])
        if not audio_path.is_file():
            audio_path = ROOT / row["audio_path"]
        if not audio_path.is_file():
            print("missing clip: {}".format(row["audio_path"]), file=sys.stderr)
            sys.exit(1)
        try:
            transcript = stt.transcribe(audio_path.read_bytes(), audio_path.name)
        except STTError as e:
            print(f"stt failed {audio_path.name}: {e}", file=sys.stderr)
            sys.exit(1)
        asr = (transcript.text or "").strip()
        true_text = row["true_transcript"]
        gold = row["gold_label"]
        if gold not in LABELS:
            print(f"bad gold_label: {gold}", file=sys.stderr)
            sys.exit(1)
        wers.append(word_error_rate(true_text, asr))
        true_label = llm_classify(true_text)["label"]
        asr_label = llm_classify(asr)["label"]
        true_hits += true_label == gold
        asr_hits += asr_label == gold
        if true_label != asr_label:
            flips.append((audio_path.name, true_label, asr_label))

    n = len(rows)
    true_acc = true_hits / n
    asr_acc = asr_hits / n
    mean_wer = sum(wers) / n
    gap = true_acc - asr_acc
    lines = [
        "| clips | WER | label acc (true transcript) | label acc (ASR transcript) | gap |",
        "| --- | --- | --- | --- | --- |",
        f"| {n} | {mean_wer:.3f} | {true_acc:.3f} | {asr_acc:.3f} | {gap:.3f} |",
        "",
        "label flips",
    ]
    if flips:
        for name, true_label, asr_label in flips:
            lines.append(f"- {name}: {true_label} -> {asr_label}")
    else:
        lines.append("- none")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
