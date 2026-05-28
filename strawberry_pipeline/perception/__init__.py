from .mock_perception import MockPerceptionModule

__all__ = ["MockPerceptionModule"]

def _lazy_import(name):
    import importlib
    return importlib.import_module(f".{name}", __package__)

def __getattr__(name):
    if name == "YoloPerceptionAdapter":
        return _lazy_import("yolo_adapter").YoloPerceptionAdapter
    if name == "YoloDevPerceptionAdapter":
        return _lazy_import("yolo_dev_adapter").YoloDevPerceptionAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
