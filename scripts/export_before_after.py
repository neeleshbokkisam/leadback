import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "eval" / "context_retries.jsonl"


def cell(value):
    if isinstance(value, list):
        value = " / ".join(str(part) for part in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def main():
    if not PATH.is_file():
        print("no rows in eval/context_retries.jsonl yet")
        sys.exit(0)
    rows = []
    for line in PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    if not rows:
        print("no rows in eval/context_retries.jsonl yet")
        sys.exit(0)
    print("| message | context | label alone | label with context |")
    print("| --- | --- | --- | --- |")
    for row in rows:
        print(
            "| {} | {} | {} | {} |".format(
                cell(row.get("text", "")),
                cell(row.get("context", "")),
                cell(row.get("label_isolated", "")),
                cell(row.get("label_context", "")),
            )
        )


if __name__ == "__main__":
    main()
