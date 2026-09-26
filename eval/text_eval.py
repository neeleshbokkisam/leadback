import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from bot.classify import llm_classify
from bot.nlp import classify_rules
from store.redis_client import LABELS

load_dotenv(ROOT / ".env")

LABELED = ROOT / "eval" / "labeled.jsonl"
OUT = ROOT / "eval" / "results_text.md"


def load_rows():
    rows = []
    for line in LABELED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def f1(golds, preds, label):
    tp = sum(g == label and p == label for g, p in zip(golds, preds))
    fp = sum(g != label and p == label for g, p in zip(golds, preds))
    fn = sum(g == label and p != label for g, p in zip(golds, preds))
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


def accuracy(golds, preds):
    return sum(g == p for g, p in zip(golds, preds)) / len(golds)


def context_of(row):
    context = row.get("context")
    if not context:
        return None
    if isinstance(context, str):
        return [context]
    return [str(line) for line in context if str(line).strip()]


def main():
    if not LABELED.is_file():
        print(f"missing {LABELED}", file=sys.stderr)
        sys.exit(1)
    rows = load_rows()
    if any(row.get("example") for row in rows):
        print("labeled.jsonl still has example rows", file=sys.stderr)
        sys.exit(1)
    if not rows:
        print("labeled.jsonl has no rows", file=sys.stderr)
        sys.exit(1)

    golds = []
    rules_preds = []
    llm_preds = []
    context_preds = []
    for row in rows:
        text = row["text"]
        gold = row["gold_label"]
        golds.append(gold)
        rules_preds.append(classify_rules(text))
        isolated = llm_classify(text)
        llm_preds.append(isolated["label"])
        context = context_of(row)
        if context:
            context_preds.append(llm_classify(text, context)["label"])
        else:
            context_preds.append(isolated["label"])

    groups = (
        ("rules", rules_preds),
        ("llm", llm_preds),
        ("llm+context", context_preds),
    )
    header = (
        "| classifier | accuracy | "
        + " | ".join(f"{label} f1" for label in LABELS)
        + " |"
    )
    sep = "| --- | --- | " + " | ".join("---" for _ in LABELS) + " |"
    lines = [header, sep]
    for name, preds in groups:
        cells = [f"{accuracy(golds, preds):.3f}"]
        cells += [f"{f1(golds, preds, label):.3f}" for label in LABELS]
        lines.append("| {} | {} |".format(name, " | ".join(cells)))
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
