"""Authenticated plugin views using the host bridge and existing database owner."""

import asyncio
import copy
import hashlib
import json
from contextlib import AsyncExitStack
from datetime import date, datetime

from astrbot.api.web import error_response, json_response, request
from astrbot.dashboard.services.config_service import validate_config

from .settings import Settings


class Dashboard:
    """Expose bounded browsing, explicit row deletion and native config reload."""

    plugin_name = "astrbot_plugin_humanization"
    categories = {"messages", "decisions", "topics", "diaries"}
    sorts = {"timestamp", "headline", "seq"}

    def __init__(self, plugin):
        self.plugin = plugin
        self.runtime = plugin.runtime
        self.database = self.runtime.storage.database
        self.sql = self.database.sql
        self.config_lock = asyncio.Lock()
        self.routes = []

    def register(self):
        for endpoint, handler, method in (
            ("overview", self.overview, "GET"),
            ("records", self.records, "GET"),
            ("records/delete", self.delete, "POST"),
            ("settings", self.settings, "GET"),
            ("settings/save", self.save_settings, "POST"),
        ):
            route = f"/{self.plugin_name}/{endpoint}"
            self.plugin.context.register_web_api(route, handler, [method], endpoint)
            self.routes.append((route, handler))

    def close(self):
        apis = self.plugin.context.registered_web_apis
        apis[:] = [api for api in apis if (api[0], api[1]) not in self.routes]

    def authorize(self):
        if not request.username:
            return error_response("需要登录 AstrBot 控制面板", status_code=403)
        if self.runtime.closed:
            return error_response("插件正在重载，请稍后刷新", status_code=503)
        return None

    @staticmethod
    def conversation(scope):
        platform, _, kind, sid = json.loads(scope)
        return f"{platform}:{'FriendMessage' if kind == 'private' else 'GroupMessage'}:{sid}"

    @staticmethod
    def revision(config):
        return hashlib.sha256(
            json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    async def overview(self):
        if denied := self.authorize():
            return denied
        scope = request.query.get("scope", "")
        async with self.database.snapshot() as tx:
            stats = (await tx.rows(self.sql["dashboard.stats"], {"scope": scope}))[0]
            scopes = await tx.rows(self.sql["dashboard.sessions"])
        return json_response(
            {
                "stats": stats,
                "sessions": [
                    {"value": row["scope"], "title": self.conversation(row["scope"])}
                    for row in scopes
                ],
                "timezone": str(self.runtime.settings.timezone),
            }
        )

    async def records(self):
        if denied := self.authorize():
            return denied
        category = request.query.get("category", "messages")
        sort = request.query.get("sort", "timestamp")
        order = request.query.get("order", "desc")
        if (
            category not in self.categories
            or sort not in self.sorts
            or order not in {"asc", "desc"}
        ):
            return error_response("无效的数据分类或排序字段")
        page = request.query.get("page", 1, type=int)
        limit = request.query.get("limit", 25, type=int)
        if page < 1 or not 1 <= limit <= 100:
            return error_response("页码或每页条数无效（最多100条）")
        start, end = request.query.get("start", ""), request.query.get("end", "")
        try:
            for value in (start, end):
                if value:
                    date.fromisoformat(value)
            if start and end and start > end:
                raise ValueError
        except ValueError:
            return error_response("日期范围无效")
        offset = (
            datetime.now(self.runtime.settings.timezone).utcoffset().total_seconds()
        )
        args = {
            "scope": request.query.get("scope", ""),
            "q": request.query.get("q", ""),
            "kind": request.query.get("kind", ""),
            "start": start,
            "end": end,
            "offset": f"{offset:+g} seconds",
            "limit": limit,
            "skip": (page - 1) * limit,
        }
        source = self.sql[f"dashboard.{category}"]
        # Only fixed resource names and whitelisted sort identifiers enter SQL.
        async with self.database.snapshot() as tx:
            total = (
                await tx.rows(self.sql["dashboard.count"].format(source=source), args)
            )[0]["total"]
            rows = await tx.rows(
                self.sql["dashboard.page"].format(
                    source=source, order=f"{sort} {order}"
                ),
                args,
            )
            for row in rows:
                row.pop("search")
                row["key"] = json.dumps([row["scope"], row["id"]], ensure_ascii=False)
                row["conversation"] = self.conversation(row["scope"])
                for field in ("segments", "decision_json", "interact"):
                    if field in row:
                        row[field] = json.loads(row[field])
                if category == "diaries":
                    row["topics"] = await tx.rows(
                        self.sql["dashboard.diary_topics"], (row["scope"], row["day"])
                    )
                    for topic in row["topics"]:
                        topic["interact"] = json.loads(topic["interact"])
        return json_response({"items": rows, "total": total})

    async def delete(self):
        """Delete explicit records while excluding concurrent plans and summaries.

        Returns:
            Actual deleted row count, or a conflict while the affected scopes are busy.
        """
        if denied := self.authorize():
            return denied
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("请求必须为对象")
        category, keys = payload.get("category"), payload.get("keys")
        if (
            not isinstance(category, str)
            or category not in self.categories
            or not isinstance(keys, list)
            or not 1 <= len(keys) <= 100
        ):
            return error_response("请选择1—100条记录")
        try:
            targets = []
            for key in keys:
                scope, identity = json.loads(key)
                self.conversation(scope)
                if category == "diaries":
                    date.fromisoformat(identity)
                elif type(identity) is not int or identity < 1:
                    raise ValueError
                targets.append((scope, identity))
            targets = list(dict.fromkeys(targets))
        except (TypeError, ValueError):
            return error_response("记录标识无效")
        scopes = sorted({scope for scope, _ in targets})
        async with self.runtime.reset_lock, AsyncExitStack() as stack:
            if self.runtime.summarizer.lock.locked() or any(
                self.runtime.controller.lock(scope).locked() for scope in scopes
            ):
                return error_response(
                    "正在回复或整理日记，请完成后重试", status_code=409
                )
            await stack.enter_async_context(self.runtime.summarizer.lock)
            for scope in scopes:
                await stack.enter_async_context(self.runtime.controller.lock(scope))
                await stack.enter_async_context(
                    self.runtime.record_locks.setdefault(scope, asyncio.Lock())
                )
            async with self.database.transaction() as tx:
                deleted = 0
                for target in targets:
                    cursor = await tx.execute(
                        self.sql[f"dashboard.delete_{category}"], target
                    )
                    deleted += cursor.rowcount
            for scope in scopes:
                self.runtime.scheduler.reset(scope)
                self.runtime.reset_versions[scope] = (
                    self.runtime.reset_versions.get(scope, 0) + 1
                )
        self.runtime.log.info(
            "dashboard.records.deleted", category=category, count=deleted
        )
        return json_response({"deleted": deleted})

    async def settings(self):
        if denied := self.authorize():
            return denied
        schema = copy.deepcopy(self.plugin.config.schema)
        providers = [
            {"title": p.meta().id, "value": p.meta().id}
            for p in self.plugin.context.get_all_providers()
        ]
        personas = [
            {"title": p.persona_id, "value": p.persona_id}
            for p in await self.plugin.context.persona_manager.get_all_personas()
        ]
        tools = [
            {"title": t.name, "value": t.name}
            for t in self.plugin.context.get_llm_tool_manager().func_list
        ]
        return json_response(
            {
                "schema": schema,
                "config": dict(self.plugin.config),
                "revision": self.revision(self.plugin.config),
                "choices": {
                    "select_provider": providers,
                    "select_persona": personas,
                    "select_tools": tools,
                },
            }
        )

    async def save_settings(self):
        """Validate the complete schema, persist it and await the host plugin reload.

        Returns:
            Save/reload result; stale edits are rejected before touching configuration.
        """
        if denied := self.authorize():
            return denied
        payload = await request.json(default={})
        if not isinstance(payload, dict) or not isinstance(payload.get("config"), dict):
            return error_response("配置必须为对象")
        async with self.config_lock:
            if payload.get("revision") != self.revision(self.plugin.config):
                return error_response(
                    "配置已被其他页面修改，请重新载入后编辑", status_code=409
                )
            config = copy.deepcopy(payload["config"])
            schema = self.plugin.config.schema
            try:
                if set(config) != set(schema) or any(
                    not isinstance(config[k], dict)
                    or set(config[k]) != set(schema[k]["items"])
                    for k in schema
                ):
                    raise ValueError("配置项不完整或包含未知字段")
                errors, config = validate_config(config, schema, False)
                if errors:
                    raise ValueError("；".join(errors))
                Settings(config)
                if (
                    config["danger"]["clear_all_data"]
                    and config["danger"]["confirmation"]
                    != self.runtime.admin.all_confirmation
                ):
                    raise ValueError("清除所有数据前必须填写正确的确认文字")
            except (ValueError, TypeError, KeyError) as exc:
                return error_response(str(exc))
            manager = self.plugin.context._star_manager
            if not any(
                star.name == self.plugin_name
                for star in self.plugin.context.get_all_stars()
            ):
                return error_response("插件未注册，无法重载", status_code=409)
            self.plugin.config.save_config(config)
            success, message = await manager.reload(self.plugin_name)
            if not success:
                return error_response(
                    f"配置已保存，但重载失败：{message}", status_code=500
                )
        return json_response({"saved": True, "reloaded": True})
