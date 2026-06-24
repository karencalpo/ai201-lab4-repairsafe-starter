import json
import os
from datetime import datetime, timezone
from config import LOG_FILE


def log_interaction(question: str, tier: str, response: str) -> None:
    """
    Append a structured record of this interaction to the audit log.

    TODO — Milestone 3:

    Before writing any code, complete specs/auditor-spec.md. The key decisions
    are what fields to log, how much of the question and response to include,
    and how to handle the logs/ directory not existing yet.

    Each record should be a JSON object written as a single line to LOG_FILE
    (defined in config.py as "logs/audit.jsonl").

    Required fields:
      - "timestamp"        : ISO 8601 datetime string
      - "tier"             : the safety tier assigned to this question
      - "question"         : the user's question (truncate to 300 chars if longer)
      - "response_preview" : first 200 characters of the response

    If the logs/ directory doesn't exist, create it before writing.

    Also print a one-line summary to the terminal so you can see logged
    interactions in real time without opening the file:
      e.g. [LOGGED] tier=caution | "How do I replace a faucet?" → 47 chars

    Design your log entry in specs/auditor-spec.md before implementing here.
    """
    # Ensure logs/ directory exists
    log_dir = os.path.dirname(LOG_FILE)
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create logs directory: {e}")
        return

    # Build the log entry with all required and additional fields
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tier": tier,
        "question": question[:300],
        "response_preview": response[:200],
        "question_length": len(question),
        "response_length": len(response),
    }

    # Write to log file as a JSON line
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except IOError as e:
        print(f"Warning: Could not write to log file: {e}")
        return

    # Print one-line terminal summary
    # Format: [YYYY-MM-DD HH:MM:SS] TIER | "question_preview..." | response_length chars
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tier_upper = tier.upper()

    # Question preview: first ~60 chars, quoted, with ... if truncated
    question_preview = question[:60]
    if len(question) > 60:
        question_preview += "..."

    print(f"[{timestamp_str}] {tier_upper} | \"{question_preview}\" | {len(response)} chars")
