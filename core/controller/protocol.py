"""Strict participation plans shared by the planner and runtime."""

import json


class ControllerProtocol:
    emotions = {
        "NEUTRAL",
        "JOY",
        "AFFECTION",
        "PRIDE",
        "ANTICIPATION",
        "SURPRISE",
        "UNCERTAINTY",
        "SADNESS",
        "ANGER",
        "AVERSION",
        "FEAR",
        "SELF_CONSCIOUS",
        "LOW_ENERGY",
        "ENVY",
    }
    styles = {
        "CUTE",
        "PLAYFUL",
        "MISCHIEVOUS",
        "SARCASTIC",
        "PASSIVE_AGGRESSIVE",
        "IRONIC",
        "DEADPAN",
        "SELF_DEPRECATING",
        "DRAMATIC",
        "ABSURD",
        "WARM",
        "COLD",
        "FLIRTATIOUS",
        "AGGRESSIVE",
        "GOOFY",
    }
    intents = {
        "REACTION",
        "ACKNOWLEDGE",
        "AGREE",
        "DISAGREE",
        "ASK",
        "PRAISE",
        "CONGRATULATE",
        "CELEBRATE",
        "COMFORT",
        "ENCOURAGE",
        "SUPPORT",
        "THANK",
        "APOLOGIZE",
        "GREET",
        "FAREWELL",
        "REQUEST",
        "REFUSE",
        "WARN",
        "TEASE",
        "TAUNT",
        "SHOW_AFFECTION",
        "SEEK_AFFECTION",
        "OBSERVE",
    }

    @classmethod
    def parse(cls, raw: str, context: dict, required: bool) -> dict:
        """Accept only complete plans referencing the provided observation.

        Args:
            raw: Unmodified JSON model response.
            context: Visible messages and topic candidates.
            required: Whether this turn must submit a native model request.

        Returns:
            Validated JSON data without truncation or schema repair.

        Raises:
            ValueError: Invalid structure, reference, enum, or conditional field.
        """
        if len(raw) > 4096:
            raise ValueError("Controller output exceeds 4096 characters")
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {
            "reply",
            "reason",
            "emotion",
            "plan",
        }:
            raise ValueError("Invalid Controller fields")
        if type(data["reply"]) is not bool or (required and not data["reply"]):
            raise ValueError("Invalid or missing required reply")
        if (
            not isinstance(data["reason"], str)
            or not data["reason"].strip()
            or len(data["reason"]) > 80
        ):
            raise ValueError("Invalid Controller reason")
        emotion = data["emotion"]
        if not isinstance(emotion, dict) or set(emotion) != {"primary", "intensity"}:
            raise ValueError("Invalid emotion fields")
        primary, intensity = emotion["primary"], emotion["intensity"]
        if (
            not isinstance(primary, str)
            or primary not in cls.emotions
            or type(intensity) is not int
            or (intensity != 0 if primary == "NEUTRAL" else not 1 <= intensity <= 3)
        ):
            raise ValueError("Invalid emotion or intensity")
        plan = data["plan"]
        if not data["reply"]:
            if plan is not None:
                raise ValueError("Silent decisions must have a null plan")
            return data
        if not isinstance(plan, dict) or set(plan) != {
            "participation",
            "target_message_id",
            "topic_id",
            "intent",
            "style",
            "guidance",
        }:
            raise ValueError("Invalid reply plan fields")
        mode = plan["participation"]
        if not isinstance(mode, str) or mode not in {
            "respond",
            "join",
            "lead",
            "start",
        }:
            raise ValueError("Invalid participation mode")
        if not isinstance(plan["intent"], str) or plan["intent"] not in cls.intents:
            raise ValueError("Invalid interaction intent")
        styles = plan["style"]
        if (
            not isinstance(styles, list)
            or len(styles) > 2
            or any(
                not isinstance(style, str) or style not in cls.styles
                for style in styles
            )
            or len(set(styles)) != len(styles)
        ):
            raise ValueError("Invalid expression styles")
        if (
            not isinstance(plan["guidance"], str)
            or not plan["guidance"].strip()
            or len(plan["guidance"]) > 300
        ):
            raise ValueError("Invalid reply guidance")
        message_id, topic_id = plan["target_message_id"], plan["topic_id"]
        if message_id is not None and (
            not isinstance(message_id, str)
            or not message_id
            or message_id not in {row["message_id"] for row in context["messages"]}
        ):
            raise ValueError("Reply target message is not visible")
        if topic_id is not None and (
            type(topic_id) is not int
            or topic_id not in {row["id"] for row in context["topics"]["items"]}
        ):
            raise ValueError("Reply target topic is not visible")
        if (mode == "respond" and message_id is None) or (
            mode in {"join", "lead"} and message_id is None and topic_id is None
        ):
            raise ValueError("Participation requires a visible focus")
        return data
