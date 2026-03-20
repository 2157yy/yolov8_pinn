from __future__ import annotations

from pathlib import Path
from typing import Any

from ..interfaces import PerceptionModule
from ..schemas import PerceptionResult


class YoloDevPerceptionAdapter(PerceptionModule):
    """Adapter boundary for the independently developed YOLO/PINN module in yolo_dev."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
        self.project_root = root
        self.yolo_dev_root = root / "yolo_dev" / "ultralytics-main"

    def analyze(self, image: Any, metadata: dict[str, Any] | None = None) -> PerceptionResult:
        raise NotImplementedError(
            "Connect this adapter to the real YOLO/PINN implementation under "
            f"{self.yolo_dev_root}. The outer agent layer should only depend on "
            "PerceptionModule and PerceptionResult."
        )
