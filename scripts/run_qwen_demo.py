from __future__ import annotations

import argparse
import json
from pathlib import Path

from strawberry_pipeline.examples import build_qwen_pipeline
from strawberry_pipeline.qwen_client import QwenChatClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Qwen-backed strawberry pipeline demo.")
    parser.add_argument("--image-id", default="demo_qwen_image_001", help="Logical image id for this demo run.")
    parser.add_argument("--plot-id", default="plot_demo", help="Plot id used for memory retrieval.")
    parser.add_argument("--plant-batch-id", default="batch_demo", help="Plant batch id used for memory retrieval.")
    parser.add_argument(
        "--storage-path",
        default="memory/qwen_demo_memory.jsonl",
        help="Path to the JSONL memory file.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print the final pipeline output as JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = QwenChatClient.from_env()
    pipeline = build_qwen_pipeline(
        client=client,
        storage_path=Path(args.storage_path),
    )
    result = pipeline.run(
        image="mock_image_for_qwen_demo",
        metadata={
            "image_id": args.image_id,
            "plot_id": args.plot_id,
            "plant_batch_id": args.plant_batch_id,
        },
    )
    output = {
        "perception": {
            "image_id": result.perception.image_id,
            "timestamp": result.perception.timestamp,
            "source": result.perception.source,
            "detection_count": len(result.perception.detections),
            "scene_summary": {
                "avg_light": result.perception.scene_summary.avg_light,
                "time_period": result.perception.scene_summary.time_period,
                "notes": result.perception.scene_summary.notes,
            },
        },
        "diagnosis": {
            "reliability": result.diagnosis.reliability,
            "confidence_score": result.diagnosis.confidence_score,
            "reason": result.diagnosis.reason,
            "evidence_points": result.diagnosis.evidence_points,
            "risks": result.diagnosis.risks,
            "recommendations": result.diagnosis.recommendations,
        },
        "decision": {
            "harvest": result.decision.harvest,
            "fill_light": result.decision.fill_light,
            "manual_review": result.decision.manual_review,
            "message": result.decision.message,
            "rationale": result.decision.rationale,
            "actions": result.decision.actions,
        },
        "history_count": len(result.history),
        "memory_path": str(Path(args.storage_path)),
    }
    if args.pretty:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
