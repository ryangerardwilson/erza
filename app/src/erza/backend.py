from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterator


Handler = Callable[..., Any]
RouteHandler = Callable[..., Any]


@dataclass(slots=True)
class RedirectResult:
    href: str


@dataclass(slots=True)
class ErrorResult:
    message: str


@dataclass(slots=True)
class RequestContext:
    session: dict[str, Any]
    method: str | None = None
    path: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


_REQUEST_CONTEXT: ContextVar[RequestContext | None] = ContextVar("erza_request_context", default=None)


class BackendError(RuntimeError):
    """Raised when the Python backend bridge cannot resolve a handler."""


def handler(name: str) -> Callable[[Handler], Handler]:
    """Attach an erza handler name to a Python callable."""

    def decorate(func: Handler) -> Handler:
        setattr(func, "_erza_handler_name", name)
        return func

    return decorate


def route(path: str, *, methods: tuple[str, ...] = ("POST",)) -> Callable[[RouteHandler], RouteHandler]:
    normalized_path = path.strip()
    if not normalized_path.startswith("/"):
        raise BackendError(f"route path must start with '/': {path}")
    normalized_methods = tuple(method.upper() for method in methods) or ("POST",)

    def decorate(func: RouteHandler) -> RouteHandler:
        setattr(func, "_erza_route_path", normalized_path)
        setattr(func, "_erza_route_methods", normalized_methods)
        return func

    return decorate


def redirect(href: str) -> RedirectResult:
    return RedirectResult(href=href)


def error(message: str) -> ErrorResult:
    return ErrorResult(message=message)


def request_context() -> RequestContext:
    context = _REQUEST_CONTEXT.get()
    if context is None:
        raise BackendError("no active erza request context")
    return context


def session() -> dict[str, Any]:
    return request_context().session


@contextmanager
def bind_request_context(
    session_state: dict[str, Any],
    *,
    method: str | None = None,
    path: str | None = None,
    data: dict[str, Any] | None = None,
) -> Iterator[RequestContext]:
    context = RequestContext(
        session=session_state,
        method=method,
        path=path,
        data=data or {},
    )
    token = _REQUEST_CONTEXT.set(context)
    try:
        yield context
    finally:
        _REQUEST_CONTEXT.reset(token)


@dataclass(slots=True)
class BackendBridge:
    handlers: dict[str, Handler]
    routes: dict[tuple[str, str], RouteHandler] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "BackendBridge":
        return cls(handlers={}, routes={})

    @classmethod
    def from_module_path(cls, path: str | Path) -> "BackendBridge":
        module_path = Path(path).resolve()
        if not module_path.exists():
            raise BackendError(f"backend module does not exist: {module_path}")

        module_name = f"erza_backend_{abs(hash(module_path))}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise BackendError(f"could not import backend module: {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        handlers, routes = _collect_handlers(module)
        return cls(handlers=handlers, routes=routes)

    def call(self, name: str, **kwargs: Any) -> Any:
        try:
            func = self.handlers[name]
        except KeyError as exc:
            raise BackendError(f"unknown backend handler: {name}") from exc
        return func(**kwargs)

    def dispatch_route(self, method: str, path: str, **kwargs: Any) -> Any:
        key = (method.upper(), path)
        try:
            func = self.routes[key]
        except KeyError as exc:
            raise BackendError(f"unknown backend route: {method.upper()} {path}") from exc
        return func(**kwargs)


def _collect_handlers(module: ModuleType) -> tuple[dict[str, Handler], dict[tuple[str, str], RouteHandler]]:
    handlers: dict[str, Handler] = {}
    routes: dict[tuple[str, str], RouteHandler] = {}

    explicit = getattr(module, "HANDLERS", None)
    if explicit is not None:
        if not isinstance(explicit, dict):
            raise BackendError("HANDLERS must be a dict[str, callable]")
        for name, func in explicit.items():
            if not callable(func):
                raise BackendError(f"HANDLERS[{name!r}] is not callable")
            handlers[str(name)] = func

    for value in vars(module).values():
        name = getattr(value, "_erza_handler_name", None)
        if name is not None:
            if not callable(value):
                raise BackendError(f"decorated handler {name!r} is not callable")
            handlers[name] = value
        route_path = getattr(value, "_erza_route_path", None)
        if route_path is not None:
            if not callable(value):
                raise BackendError(f"decorated route {route_path!r} is not callable")
            for method in getattr(value, "_erza_route_methods", ("POST",)):
                routes[(method.upper(), route_path)] = value

    return handlers, routes
