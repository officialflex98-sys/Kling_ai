"""
Picks the next topic to make a video about.

Strategy: reads topics.txt top to bottom, skipping anything already recorded
in used_topics.json, so a daily cron run never repeats a topic. When the
backlog runs dry it just starts over from the top.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
TOPICS_FILE = ROOT / "topics.txt"
USED_FILE = ROOT / "used_topics.json"


def _load_used() -> list[str]:
    if not USED_FILE.exists():
        return []
    with open(USED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_used(used: list[str]) -> None:
    with open(USED_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, indent=2)


def pick_topic(explicit_topic: str | None = None) -> str:
    """Returns the topic to use this run. If explicit_topic is given
    (e.g. from --topic on the CLI), that always wins and is not recorded
    against the backlog, so manual runs don't burn through topics.txt."""
    if explicit_topic:
        return explicit_topic.strip()

    if not TOPICS_FILE.exists():
        raise FileNotFoundError(
            f"No topics.txt found at {TOPICS_FILE}. Add one topic per line."
        )

    all_topics = [
        line.strip()
        for line in TOPICS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all_topics:
        raise ValueError("topics.txt is empty. Add at least one topic.")

    used = _load_used()
    remaining = [t for t in all_topics if t not in used]

    if not remaining:
        # Backlog exhausted -> start over
        used = []
        remaining = all_topics

    chosen = remaining[0]
    used.append(chosen)
    _save_used(used)

    log_entry = f"{datetime.now(timezone.utc).isoformat()} :: {chosen}"
    log_path = ROOT / "logs" / "topic_history.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

    return chosen


if __name__ == "__main__":
    os.makedirs(ROOT / "logs", exist_ok=True)
    print(pick_topic())
