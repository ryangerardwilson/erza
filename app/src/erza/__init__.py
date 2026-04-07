"""erza v0 prototype package."""

__all__ = ["__version__"]

try:
    from _version import __version__
except ModuleNotFoundError:
    import importlib.util
    from pathlib import Path

    _version_file = Path(__file__).resolve().parents[2] / "_version.py"
    _spec = importlib.util.spec_from_file_location("erza_runtime_version", _version_file)
    if _spec is None or _spec.loader is None:
        raise RuntimeError(f"unable to load runtime version from {_version_file}")
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    __version__ = _module.__version__
