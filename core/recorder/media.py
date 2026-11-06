"""Persist event attachments and describe small conversation batches."""

import asyncio
import ipaddress
import json
import mimetypes
import re
import socket
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from ...models.resource import Resource


def public_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.username
        or parsed.password
        or not parsed.hostname
    ):
        raise ValueError("Unsupported attachment URL")
    addresses = socket.getaddrinfo(
        parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
    )
    if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Attachment URL resolves to a non-public address")


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Media:
    TEXT_SUFFIXES = {
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".py",
        ".js",
        ".ts",
        ".css",
        ".html",
        ".xml",
        ".toml",
        ".ini",
        ".log",
        ".sql",
        ".java",
        ".c",
        ".cpp",
        ".rs",
        ".go",
    }

    def __init__(self, storage, settings, context, log):
        self.storage, self.settings, self.context, self.log = (
            storage,
            settings,
            context,
            log,
        )
        self.root = storage.path.parent.parent
        self.lock = asyncio.Lock()
        self.capturing = {}
        self.prompt = (
            Path(__file__).resolve().parents[2] / "resource/prompts/media.txt"
        ).read_text(encoding="utf-8")

    def path(self, relative):
        path = (self.root / relative).resolve()
        if path.parent not in {
            (self.root / k).resolve() for k in ("image", "record", "video", "file")
        }:
            raise ValueError("Invalid managed resource path")
        return path

    async def cleanup(self):
        for row in await self.storage.rows(self.storage.sql["resources.cleanup"]):
            try:
                await asyncio.to_thread(self.path(row["path"]).unlink, missing_ok=True)
                async with self.storage.database.transaction() as tx:
                    await tx.execute(
                        self.storage.sql["resources.cleaned"], (row["path"],)
                    )
            except OSError:
                self.log.warning("media.cleanup.failed")

    async def recover(self):
        """Remove only our interrupted copies, never host or user named files."""
        paths = {
            r["path"]
            for r in await self.storage.rows(self.storage.sql["resources.paths"])
        }
        for kind in ("image", "record", "video", "file"):
            folder = self.root / kind
            folder.mkdir(parents=True, exist_ok=True)
            for path in folder.iterdir():
                relative = f"{kind}/{path.name}"
                if (
                    re.fullmatch(r"[0-9a-f]{32}\.[a-z0-9]{1,9}", path.name)
                    and relative not in paths
                ):
                    await asyncio.to_thread(path.unlink, missing_ok=True)
        await self.cleanup()
        for row in await self.storage.rows(self.storage.sql["resources.owners"]):
            await self.render(row["message_row"])

    def copy(self, source, target):
        limit = int(self.settings.recorder.get("media_max_mb", 50)) * 1024 * 1024
        target.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        try:
            if str(source).startswith(("https://", "http://")):
                public_url(source)
                stream = build_opener(PublicRedirect()).open(source, timeout=15)
            else:
                stream = open(source, "rb")
            with stream as src, target.open("xb") as dst:
                while chunk := src.read(65536):
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("Resource exceeds storage limit")
                    dst.write(chunk)
            return size
        except BaseException:
            target.unlink(missing_ok=True)
            raise

    async def action(self, row, action, **kwargs):
        platform = self.context.get_platform_inst(row["platform"])
        if not platform:
            return {}
        async with asyncio.timeout(8):
            result = await platform.get_client().call_action(action, **kwargs)
        return result.get("data", result) if isinstance(result, dict) else {}

    async def capture(self, message, parts, raw=None):
        # Recover STT provenance only when raw and normalized positions agree.
        original = raw.get("message") if isinstance(raw, dict) else None
        if (
            isinstance(original, list)
            and len(original) == len(parts)
            and all(
                isinstance(segment, dict)
                and (
                    segment.get("type") == part.type.lower()
                    or (
                        segment.get("type") in ("text", "record")
                        and part.type.lower() == "plain"
                    )
                )
                for segment, part in zip(original, parts)
            )
        ):
            from astrbot.api.message_components import Record

            parts = list(parts)
            for i, segment in enumerate(original):
                if segment.get("type") == "record" and parts[i].type.lower() == "plain":
                    data = segment.get("data", {})
                    parts[i] = Record(
                        file=data.get("url") or data.get("file", ""), text=parts[i].text
                    )
        if not any(
            p.type.lower() in ("image", "record", "video", "file", "forward")
            or re.search(r"https?://", getattr(p, "text", "") or "")
            for p in parts
        ):
            return
        self.capturing[message.scope] = self.capturing.get(message.scope, 0) + 1
        try:
            await self._capture(message, parts)
        finally:
            self.capturing[message.scope] -= 1
            if not self.capturing[message.scope]:
                del self.capturing[message.scope]

    async def _capture(self, message, parts):
        rows = await self.storage.rows(
            self.storage.sql["resources.message"],
            (message.scope, message.direction, message.message_id),
        )
        if not rows:
            return
        row = rows[0]
        segments = json.loads(row["segments"])
        async with self.lock:
            existing = await self.storage.rows(
                self.storage.sql["resources.for_message"], (row["id"],)
            )
            if existing:
                return
            for position, part in enumerate(parts):
                kind = part.type.lower()
                if kind not in ("image", "record", "video", "file", "forward"):
                    continue
                r = Resource(
                    uuid.uuid4().hex, kind, str(getattr(part, "name", "") or kind)
                )
                r.description = r.name
                transcript = getattr(part, "text", "") if kind == "record" else ""
                try:
                    if kind == "forward":
                        r.source = str(getattr(part, "id", "") or "")
                        if r.source:
                            data = await self.action(
                                row, "get_forward_msg", id=r.source
                            )
                            content = json.dumps(
                                data.get("messages", [])[:30], ensure_ascii=False
                            )[:12000]
                            r.path = f"file/{r.id}.txt"
                            target = self.path(r.path)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            await asyncio.to_thread(
                                target.write_text, content, encoding="utf-8"
                            )
                            r.size = target.stat().st_size
                            r.status = "pending"
                    else:
                        source = (
                            getattr(part, "url", "") or getattr(part, "file", "") or ""
                        )
                        if not str(source).startswith(("http://", "https://")):
                            async with asyncio.timeout(30):
                                source = await (
                                    part.get_file()
                                    if kind == "file"
                                    else part.convert_to_file_path()
                                )
                        r.name = str(
                            getattr(part, "name", "")
                            or Path(urlsplit(str(source)).path).name
                            or kind
                        )
                        r.source = str(source)
                        suffix = Path(r.name).suffix.lower()
                        if not suffix or len(suffix) > 10 or not suffix[1:].isalnum():
                            suffix = ".bin"
                        r.path = f"{kind}/{r.id}{suffix}"
                        # Complete the copy before event-scoped source cleanup.
                        job = asyncio.create_task(
                            asyncio.to_thread(self.copy, source, self.path(r.path))
                        )
                        try:
                            r.size = await asyncio.shield(job)
                        except asyncio.CancelledError:
                            await job
                            self.path(r.path).unlink(missing_ok=True)
                            raise
                        r.description = r.name
                        r.status = "pending" if kind != "video" else "skipped"
                except Exception:
                    r.path, r.status = "", "failed"
                    self.log.warning("media.capture.failed", kind=kind)
                if transcript:
                    r.description, r.status = transcript, "ready"
                if not self.settings.recorder.get(
                    "media_enabled", True
                ) or self.settings.scope_action(
                    message.umo, f"{message.platform}:GroupMessage:{message.group_id}"
                ) not in ("active", "observe"):
                    if r.status == "pending":
                        r.status = "skipped"
                try:
                    async with self.storage.database.transaction() as tx:
                        inserted = await tx.execute(
                            self.storage.sql["resources.insert"],
                            (
                                r.id,
                                position,
                                kind,
                                r.name,
                                r.path,
                                r.size,
                                r.source,
                                time.time(),
                                r.status,
                                r.description,
                                mimetypes.guess_type(r.name)[0]
                                or "application/octet-stream",
                                row["id"],
                            ),
                        )
                    if not inserted.rowcount:
                        if r.path:
                            self.path(r.path).unlink(missing_ok=True)
                        continue
                except BaseException:
                    if r.path:
                        self.path(r.path).unlink(missing_ok=True)
                    raise
                if position < len(segments):
                    segments[position] = {"type": kind, "resource_id": r.id}
                    if kind == "record" and getattr(part, "text", None):
                        segments[position]["text"] = part.text
            expanded = []
            link_index = len(parts)
            for segment in segments:
                if segment.get("type") != "text":
                    expanded.append(segment)
                    continue
                text = segment.get("text", "")
                end = 0
                for match in list(re.finditer(r'https?://[^\s<>"\u3000]+', text))[:8]:
                    if match.start() > end:
                        expanded.append(
                            {"type": "text", "text": text[end : match.start()]}
                        )
                    rid = uuid.uuid4().hex
                    url = match.group()
                    async with self.storage.database.transaction() as tx:
                        await tx.execute(
                            self.storage.sql["resources.insert"],
                            (
                                rid,
                                link_index,
                                "link",
                                url,
                                "",
                                0,
                                url,
                                time.time(),
                                "skipped",
                                url,
                                "text/uri-list",
                                row["id"],
                            ),
                        )
                    expanded.append({"type": "link", "resource_id": rid})
                    link_index += 1
                    end = match.end()
                if end < len(text) or not text:
                    expanded.append({"type": "text", "text": text[end:]})
            await self.render(row["id"], expanded)

    async def render(self, message_id, segments=None):
        async with self.storage.database.transaction() as tx:
            rows = await tx.rows(self.storage.sql["resources.by_id"], (message_id,))
            if not rows:
                return
            segments = (
                segments if segments is not None else json.loads(rows[0]["segments"])
            )
            resources = {
                r["id"]: r
                for r in await tx.rows(
                    self.storage.sql["resources.for_message"], (message_id,)
                )
            }
            linked = {s.get("resource_id") for s in segments}
            for r in resources.values():
                if r["id"] not in linked and r["position"] < len(segments):
                    old = segments[r["position"]]
                    segments[r["position"]] = {
                        "type": r["kind"],
                        "resource_id": r["id"],
                    }
                    if r["kind"] == "record" and old.get("text"):
                        segments[r["position"]]["text"] = old["text"]
            rendered = []
            skip_text = None
            for s in segments:
                r = resources.get(s.get("resource_id"))
                if r:
                    pending = "（待转述）" if r["status"] == "pending" else ""
                    rendered.append(
                        f"[{r['kind']}:{r['id']}]{r['description']}{pending}"
                    )
                    skip_text = s.get("text") if r["kind"] == "record" else None
                elif s["type"] == "text":
                    if s.get("text") != skip_text:
                        rendered.append(s.get("text", ""))
                    skip_text = None
                elif s["type"] == "at":
                    rendered.append(f"[@{s['id']}]")
                elif s["type"] == "poke":
                    rendered.append(
                        f"[poke：发送者QQ={s.get('sender_id')}；目标QQ={s.get('target_id') or '未知'}]"
                    )
                else:
                    rendered.append(f"[{s['type']}]")
            await tx.execute(
                self.storage.sql["resources.render"],
                (
                    "".join(rendered),
                    json.dumps(segments, ensure_ascii=False),
                    message_id,
                ),
            )

    async def finish(self, row, description, status="ready", provider=""):
        async with self.storage.database.transaction() as tx:
            await tx.execute(
                self.storage.sql["resources.finish"],
                (description, status, provider, time.time(), row["id"]),
            )
        await self.render(row["message_row"])

    async def stt(self, row):
        provider = await self.context.get_using_stt_provider_async(row["umo"])
        if not provider or not row["path"]:
            return ""
        async with asyncio.timeout(30):
            return await provider.get_text(audio_url=str(self.path(row["path"])))

    async def batch(self, rows):
        provider_id = (
            self.settings.recorder.get("media_provider", "")
            or self.settings.recorder["summary_provider"]
        )
        try:
            provider = (
                self.context.get_provider_by_id(provider_id) if provider_id else None
            )
        except (ValueError, KeyError):
            provider = None
        modalities = set(
            (provider.provider_config.get("modalities") or []) if provider else []
        )
        items, images, audios, selected = [], [], [], []
        text_budget = 16000
        for row in rows:
            if text_budget == 0 and row["kind"] in ("file", "forward"):
                break
            enabled = self.settings.recorder.get(
                "media_enabled", True
            ) and self.settings.scope_action(
                row["umo"], f"{row['platform']}:GroupMessage:{row['group_id']}"
            ) in ("active", "observe")
            if not enabled:
                await self.finish(row, row["description"], "skipped")
                continue
            item = {"id": row["id"], "type": row["kind"], "name": row["name"]}
            try:
                if row["kind"] == "record":
                    result = await self.action(
                        row, "fetch_ptt_text", message_id=row["message_id"]
                    )
                    if result.get("text"):
                        await self.finish(row, result["text"], provider="adapter_stt")
                        continue
            except Exception:
                pass
            try:
                if row["kind"] == "image" and "image" in modalities:
                    images.append(str(self.path(row["path"])))
                    item["image_index"] = len(images)
                elif row["kind"] == "record" and "audio" in modalities:
                    audios.append(str(self.path(row["path"])))
                    item["audio_index"] = len(audios)
                elif row["kind"] == "record":
                    text = await self.stt(row)
                    await self.finish(
                        row,
                        text or row["description"],
                        "ready" if text else "skipped",
                        "native_stt",
                    )
                    continue
                elif (
                    row["kind"] == "file"
                    and row["size"] < 1000000
                    and Path(row["name"]).suffix.lower() in self.TEXT_SUFFIXES
                ):
                    item["text"] = await asyncio.to_thread(
                        self.read_text, self.path(row["path"])
                    )
                elif row["kind"] == "forward":
                    item["text"] = await asyncio.to_thread(
                        self.read_text, self.path(row["path"])
                    )
                else:
                    await self.finish(row, row["description"], "skipped")
                    continue
                if "text" in item:
                    content = item["text"]
                    item["text"] = content[:text_budget]
                    if len(content) > text_budget:
                        item["text"] += "\n[批次字数预算已截断]"
                    text_budget = max(0, text_budget - len(content))
                selected.append(row)
                items.append(item)
            except Exception:
                await self.finish(row, row["description"], "failed")
        if not selected:
            return
        started = time.monotonic()
        self.log.info("media.batch.start", count=len(selected))
        results = {}
        if provider:
            try:
                async with asyncio.timeout(60):
                    response = await self.context.llm_generate(
                        chat_provider_id=provider_id,
                        system_prompt=self.prompt,
                        prompt=json.dumps(items, ensure_ascii=False),
                        image_urls=images,
                        audio_urls=audios,
                    )
                decoded = json.loads(response.completion_text)
                if isinstance(decoded, dict):
                    results = decoded
            except Exception:
                self.log.warning("media.batch.failed", count=len(selected))
        for row in selected:
            used_provider = provider_id
            text = results.get(row["id"])
            if not isinstance(text, str) or not text.strip():
                text = ""
                if row["kind"] == "record":
                    try:
                        text = await self.stt(row)
                        used_provider = "native_stt"
                    except Exception:
                        pass
            await self.finish(
                row,
                text[:4000] if text else row["description"],
                "ready" if text else "failed",
                used_provider,
            )
        self.log.info(
            "media.batch.complete",
            count=len(selected),
            duration_seconds=round(time.monotonic() - started, 2),
        )

    @staticmethod
    def read_text(path):
        with path.open("rb") as stream:
            data = stream.read(48001)
        text = data[:48000].decode("utf-8-sig", errors="replace")
        return text[:12000] + (
            "\n[内容已截断]" if len(data) > 48000 or len(text) > 12000 else ""
        )

    async def waiting(self, scope):
        if self.capturing.get(scope):
            return True
        return (
            await self.storage.rows(self.storage.sql["resources.waiting"], (scope,))
        )[0]["n"] > 0

    async def wait(self, scope):
        for _ in range(16):
            if not await self.waiting(scope):
                return
            await asyncio.sleep(0.5)

    async def run(self):
        while True:
            await asyncio.sleep(2)
            try:
                async with self.lock:
                    rows = await self.storage.rows(
                        self.storage.sql["resources.pending"]
                    )
                if rows:
                    scope = rows[0]["scope"]
                    await self.batch([r for r in rows if r["scope"] == scope][:6])
                await self.cleanup()
            except Exception:
                self.log.exception("media.worker.failed")
