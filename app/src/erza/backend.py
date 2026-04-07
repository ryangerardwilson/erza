from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


Handler = Callable[..., Any]


class BackendError(RuntimeError):
    """Raised when the Python backend bridge cannot resolve a handler."""


def handler(name: str) -> Callable[[Handler], Handler]:
    """Attach an erza handler name to a Python callable."""

    def decorate(func: Handler) -> Handler:
        setattr(func, "_erza_handler_name", name)
        return func

    return decorate


@dataclass(slots=True)
class BackendBridge:
    handlers: dict[str, Handler]

    @classmethod
    def empty(cls) -> "BackendBridge":
        return cls(handlers={})

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
        return cls(handlers=_collect_handlers(module))

    def call(self, name: str, **kwargs: Any) -> Any:
        try:
            func = self.handlers[name]
        except KeyError as exc:
            raise BackendError(f"unknown backend handler: {name}") from exc
        return func(**kwargs)


def _collect_handlers(module: ModuleType) -> dict[str, Handler]:
    handlers: dict[str, Handler] = {}

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

    return handlers
