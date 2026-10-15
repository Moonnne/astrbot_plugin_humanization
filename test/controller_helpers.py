"""Controller plan fixtures for protocol and native runtime tests."""

import json


def plan_data(
    reply=True, target="1", guidance="简短接话", emotion="NEUTRAL", intensity=0
):
    return {
        "reply": reply,
        "reason": "符合当前话题。",
        "emotion": {"primary": emotion, "intensity": intensity},
        "plan": {
            "participation": "respond",
            "target_message_id": target,
            "topic_id": None,
            "intent": "REACTION",
            "style": [],
            "guidance": guidance,
        }
        if reply
        else None,
    }


def plan_json(**kwargs):
    return json.dumps(plan_data(**kwargs), ensure_ascii=False)
