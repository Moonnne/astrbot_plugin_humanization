"""Opt-in, reversible instrumentation confined to plugin-owned callables."""

import functools
import inspect
import sys
import time
from contextlib import contextmanager
from pathlib import Path


def log_context(prefix):
    """Correlate an async business operation without changing its outcome.

    Args:
        prefix: Correlation ID category.

    Returns:
        Decorator for an instance method with a PluginLog member.
    """

    def decorate(function):
        @functools.wraps(function)
        async def wrapped(self, *args, **kwargs):
            async with self.log.context(prefix):
                return await function(self, *args, **kwargs)

        return wrapped

    return decorate


class CallTracker:
    """Install wrappers only while TRACK is selected; never profile the host.

    Args:
        log: Owning PluginLog instance.
    """

    def __init__(self, log):
        self.log = log
        self.restores = []
        self.wrappers = {}

    def install(self, package):
        root = Path(__file__).resolve().parents[1]
        modules = [
            module
            for name, module in list(sys.modules.items())
            if name.startswith(package + ".")
            and not name.endswith((".plugin_log", ".log_tracking"))
        ]
        for module in modules:
            for name, value in list(vars(module).items()):
                if inspect.isfunction(value) and self._owned(value, root):
                    self._replace(module, name, self._wrap(value))
                elif inspect.isclass(value) and value.__module__ == module.__name__:
                    for key, member in list(vars(value).items()):
                        if isinstance(member, (classmethod, staticmethod)):
                            if self._owned(member.__func__, root):
                                self._replace(
                                    value,
                                    key,
                                    type(member)(self._wrap(member.__func__)),
                                )
                        elif isinstance(member, property):
                            functions = tuple(
                                self._wrap(f) if f and self._owned(f, root) else f
                                for f in (member.fget, member.fset, member.fdel)
                            )
                            self._replace(
                                value, key, property(*functions, doc=member.__doc__)
                            )
                        elif inspect.isfunction(member) and self._owned(member, root):
                            self._replace(value, key, self._wrap(member))

        from astrbot.core.star.star_handler import star_handlers_registry

        for handler in star_handlers_registry:
            if handler.handler in self.wrappers:
                self._replace(handler, "handler", self.wrappers[handler.handler])

    @staticmethod
    def _owned(function, root):
        # Exclude generated dataclass methods and imported library functions.
        if function.__module__.endswith((".plugin_log", ".log_tracking")):
            return False
        code = getattr(inspect.unwrap(function), "__code__", None)
        return bool(code and Path(code.co_filename).is_relative_to(root))

    def _replace(self, owner, name, replacement):
        previous = vars(owner)[name]
        setattr(owner, name, replacement)
        self.restores.append((owner, name, previous, replacement))

    @staticmethod
    def summary(value):
        # Never repr arbitrary objects or materialize iterators.
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, (str, bytes, dict, list, tuple, set)):
            return f"{type(value).__name__}(count={len(value)})"
        return type(value).__name__

    @contextmanager
    def _call(self, function, args, kwargs):
        original = inspect.unwrap(function)
        source = (
            original.__code__.co_filename,
            original.__code__.co_firstlineno,
            original.__name__,
        )
        frame = sys._getframe(3)
        caller = f"{frame.f_globals.get('__name__', '')}.{frame.f_code.co_name}"
        target = f"{function.__module__}.{function.__qualname__}"
        started = time.perf_counter()
        result = {}
        self.log.track(
            "track.call",
            source,
            caller=caller,
            target=target,
            arguments_count=len(args) + len(kwargs),
        )
        try:
            yield result
        except BaseException as exc:
            self.log.track(
                "track.error",
                source,
                target=target,
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
            )
            raise
        else:
            self.log.track(
                "track.return",
                source,
                target=target,
                return_summary=result.get("value", "completed"),
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
            )

    def _wrap(self, function):
        if function in self.wrappers:
            return self.wrappers[function]
        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def wrapped(*args, **kwargs):
                with self._call(function, args, kwargs) as outcome:
                    result = await function(*args, **kwargs)
                    outcome["value"] = self.summary(result)
                    return result
        elif inspect.isasyncgenfunction(function):

            @functools.wraps(function)
            async def wrapped(*args, **kwargs):
                with self._call(function, args, kwargs) as outcome:
                    generator = function(*args, **kwargs)
                    yielded = 0
                    try:
                        try:
                            value = await generator.__anext__()
                            while True:
                                yielded += 1
                                try:
                                    sent = yield value
                                except GeneratorExit:
                                    raise
                                except BaseException as exc:
                                    value = await generator.athrow(exc)
                                else:
                                    value = await generator.asend(sent)
                        except StopAsyncIteration:
                            outcome["value"] = f"async_generator(yields={yielded})"
                    finally:
                        await generator.aclose()
        elif inspect.isgeneratorfunction(function):

            @functools.wraps(function)
            def wrapped(*args, **kwargs):
                with self._call(function, args, kwargs) as outcome:
                    result = yield from function(*args, **kwargs)
                    outcome["value"] = self.summary(result)
                    return result
        else:

            @functools.wraps(function)
            def wrapped(*args, **kwargs):
                with self._call(function, args, kwargs) as outcome:
                    result = function(*args, **kwargs)
                    outcome["value"] = self.summary(result)
                    return result

        self.wrappers[function] = wrapped
        return wrapped

    def close(self):
        for owner, name, previous, replacement in reversed(self.restores):
            if vars(owner).get(name) is replacement:
                setattr(owner, name, previous)
        self.restores.clear()
        self.wrappers.clear()
