"""Structured diary changes and deterministic readable topic rendering."""

import json


class DiaryProtocol:
    fields = {"topic", "interact", "reply", "reaction"}

    @classmethod
    def parse(cls, raw, messages, diaries, cursor, day, limit):
        """Validate a complete model batch before any database writes.

        Args:
            raw: JSON response containing only a changes list.
            messages: Provided message records, including local formatted time.
            diaries: Provided diary days and editable topic IDs.
            cursor: Last successfully summarized message sequence.
            day: Current diary date.
            limit: Maximum response character count.

        Returns:
            Validated changes with server-derived source and time metadata.

        Raises:
            ValueError: Invalid schema, evidence, target, or output length.
        """
        if len(raw) > limit:
            raise ValueError("Diary response exceeds the output character limit")
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"changes"}:
            raise ValueError("Expected a diary changes object")
        if not isinstance(data["changes"], list):
            raise ValueError("Diary changes must be a list")
        sources = {row["seq"]: row for row in messages}
        editable = {
            topic["id"]
            for diary in diaries
            if diary["day"] == day and not diary["sealed"]
            for topic in diary["topics"]
        }
        updated = set()
        changes = []
        for change in data["changes"]:
            if not isinstance(change, dict):
                raise ValueError("Diary change must be an object")
            action = change.get("action")
            required = {"action", "evidence_seqs"}
            if action == "add":
                required |= cls.fields
                allowed = required
            elif action == "update":
                required |= {"id"}
                allowed = required | cls.fields
                target = change.get("id")
                if (
                    type(target) is not int
                    or target not in editable
                    or target in updated
                ):
                    raise ValueError("Diary update target is unavailable or repeated")
                updated.add(target)
            else:
                raise ValueError("Unknown diary action")
            if (
                not required <= change.keys() <= allowed
                or not cls.fields & change.keys()
            ):
                raise ValueError("Invalid diary change fields")
            evidence = change["evidence_seqs"]
            if (
                not isinstance(evidence, list)
                or not evidence
                or any(type(seq) is not int or seq not in sources for seq in evidence)
                or not any(seq > cursor for seq in evidence)
            ):
                raise ValueError("Diary changes require provided new message evidence")
            for field in cls.fields & change.keys():
                value = change[field]
                if field == "interact":
                    if not isinstance(value, list) or any(
                        not isinstance(line, str) or not line.strip() for line in value
                    ):
                        raise ValueError("Diary interactions must be short text lines")
                elif not isinstance(value, str) or not value.strip():
                    raise ValueError("Diary text fields must be nonempty strings")
            item = {
                key: value for key, value in change.items() if key != "evidence_seqs"
            }
            item.update(first_seq=min(evidence), last_seq=max(evidence))
            if action == "add":
                source = sources[min(evidence)]
                item.update(topic_at=source["sent_at"], topic_time=source["local_time"])
            changes.append(item)
        return changes

    @staticmethod
    def render_topic(topic):
        return "\n".join(
            (
                f"[Time]{topic['topic_time']}",
                f"[Topic]{topic['topic']}",
                "[Interact]",
                *(f"- {line}" for line in topic["interact"]),
                f"[Reply]{topic['reply']}",
                f"[Reaction]{topic['reaction']}",
            )
        )
