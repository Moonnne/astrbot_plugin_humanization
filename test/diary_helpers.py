"""Diary fixtures for storage and model-response tests."""

import json


def topic_change(text, seq=1):
    return {
        "action": "add",
        "topic": text,
        "interact": [text],
        "reply": "未见我参与",
        "reaction": "未见明确反应",
        "first_seq": seq,
        "last_seq": seq,
        "topic_at": float(seq),
        "topic_time": "2026-10-15 08:00 +0800",
    }


def model_change(text, seq=1):
    change = topic_change(text, seq)
    for key in ("first_seq", "last_seq", "topic_at", "topic_time"):
        change.pop(key)
    change["evidence_seqs"] = [seq]
    return json.dumps({"changes": [change]}, ensure_ascii=False)
