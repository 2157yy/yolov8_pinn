#!/usr/bin/env python3
"""Unified bridge: strawberry maturity detection + Qwen analysis in one call.

Reads a JSON request from stdin, runs YOLO inference on the specified image,
then feeds the real detection results as context to Qwen for conversational
analysis. Supports both one-shot and SSE streaming modes.

Input::

    {
      "image_path": "/path/to/strawberry.jpg",
      "message": "这张图里的草莓成熟度怎么样？",
      "messages": [{"role": "user", "content": "..."}],
      "model_path": "models/strawberry-maturity-s-best.pt",
      "conf_threshold": 0.25,
      "stream": false,
      "history": [...]
    }

Output (non-streaming)::

    {"success": true, "reply": "...", "detection_count": 2, "detections": [...]}

Output (streaming): SSE lines with type=ready/thinking/answer/done/error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# system prompt builder
# ---------------------------------------------------------------------------

def build_maturity_system_prompt(
    detections: list[dict[str, Any]],
    counts: dict[str, int],
) -> str:
    """Build a maturity-focused system prompt from real YOLO maturity results."""
    if detections:
        lines = ["检测到以下草莓成熟度目标：", ""]
        for i, d in enumerate(detections, 1):
            lines.append(
                f"  {i}. {d['class_name']} — 置信度 {d['confidence']:.2%}，"
                f"位置 bbox=[{d['bbox']['x1']:.0f}, {d['bbox']['y1']:.0f}, "
                f"{d['bbox']['x2']:.0f}, {d['bbox']['y2']:.0f}]"
            )
        lines.append("")
        lines.append(
            "统计结果："
            f"半熟 {counts.get('halfripe', 0)} 个，"
            f"成熟 {counts.get('ripe', 0)} 个，"
            f"未熟 {counts.get('unripe', 0)} 个。"
        )
    else:
        lines = ["未检测到可用的草莓成熟度目标。"]

    return (
        "你是一位草莓成熟度分析专家。"
        "请根据以下YOLO实时检测结果，用中文回答用户关于草莓成熟度、采摘时机、果实分布和管理建议的问题。"
        "包括但不限于：成熟/半熟/未熟占比、是否适合采摘、是否建议分批采收、是否需要人工复核。"
        "如果检测结果不确定或置信度较低，请诚实说明。"
        "不要编造检测结果中没有的成熟度信息。\n\n"
        "当前检测结果：\n"
        + "\n".join(lines)
    )


# ---------------------------------------------------------------------------
# detection helpers
# ---------------------------------------------------------------------------

def run_detection(image_path: str, model_path: str, conf_threshold: float) -> dict[str, Any]:
    """Run maturity inference and return serialisable detection data."""
    from strawberry_maturity_bridge import load_model, run_maturity_inference

    model = load_model(model_path)
    inference = run_maturity_inference(image_path, model, conf_threshold)

    return {
        "image_id": Path(image_path).stem,
        "detections": inference["detections"],
        "detection_count": len(inference["detections"]),
        "counts": inference["counts"],
    }


# ---------------------------------------------------------------------------
# Qwen chat
# ---------------------------------------------------------------------------

def build_chat_response(payload: dict[str, Any]) -> dict[str, Any]:
    from strawberry_pipeline.qwen_client import QwenChatClient

    image_path = payload["image_path"]
    model_path = payload.get("model_path", "models/strawberry-maturity-s-best.pt")
    conf_threshold = float(payload.get("conf_threshold", 0.25))

    detection = run_detection(image_path, model_path, conf_threshold)

    client = QwenChatClient.from_env()
    system_prompt = build_maturity_system_prompt(detection["detections"], detection["counts"])

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    history = payload.get("messages")
    if isinstance(history, list):
        for item in history:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

    if not any(m["role"] == "user" for m in messages):
        message = str(payload.get("message", "")).strip()
        if message:
            messages.append({"role": "user", "content": message})

    reply = client.chat(messages=messages)

    return {
        "success": True,
        "reply": reply,
        "detection_count": detection["detection_count"],
        "detections": detection["detections"],
        "counts": detection["counts"],
        "image_id": detection["image_id"],
    }


# ---------------------------------------------------------------------------
# streaming helpers
# ---------------------------------------------------------------------------

def _write_event(event: dict[str, Any]) -> None:
    line = json.dumps(event, ensure_ascii=False) + "\n"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(line.encode("utf-8"))
    else:
        sys.stdout.write(line)
    sys.stdout.flush()


def stream_chat_response(payload: dict[str, Any]) -> None:
    from strawberry_pipeline.qwen_client import QwenChatClient

    image_path = payload["image_path"]
    model_path = payload.get("model_path", "models/strawberry-maturity-s-best.pt")
    conf_threshold = float(payload.get("conf_threshold", 0.25))

    # 1. Run detection
    _write_event({"type": "status", "stage": "detecting", "message": "正在运行 YOLO 草莓成熟度检测..."})
    detection = run_detection(image_path, model_path, conf_threshold)

    # 2. Send detection summary
    _write_event({
        "type": "ready",
        "detection_count": detection["detection_count"],
        "detections": detection["detections"],
        "counts": detection["counts"],
        "image_id": detection["image_id"],
    })

    # 3. Build system prompt and call Qwen
    client = QwenChatClient.from_env()
    system_prompt = build_maturity_system_prompt(detection["detections"], detection["counts"])

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    history = payload.get("messages")
    if isinstance(history, list):
        for item in history:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

    if not any(m["role"] == "user" for m in messages):
        message = str(payload.get("message", "")).strip()
        if message:
            messages.append({"role": "user", "content": message})

    reply_parts: list[str] = []
    reasoning_parts: list[str] = []

    for chunk in client.chat_stream(
        messages=messages,
        extra_body={"enable_thinking": True},
    ):
        if chunk.get("type") == "chunk":
            reasoning_delta = str(chunk.get("reasoning_delta") or "")
            content_delta = str(chunk.get("content_delta") or "")

            if reasoning_delta:
                reasoning_parts.append(reasoning_delta)
                _write_event({"type": "thinking", "delta": reasoning_delta})

            if content_delta:
                reply_parts.append(content_delta)
                _write_event({"type": "answer", "delta": content_delta})

        if chunk.get("type") == "usage" and chunk.get("usage"):
            _write_event({"type": "usage", "usage": chunk["usage"]})

        if chunk.get("type") == "done":
            break

    _write_event({
        "type": "done",
        "reply": "".join(reply_parts),
        "reasoning": "".join(reasoning_parts),
        "detection_count": detection["detection_count"],
        "detections": detection["detections"],
        "counts": detection["counts"],
    })


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"success": False, "error": "Empty stdin input"}))
        return 1

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {exc}"}))
        return 1

    image_path = payload.get("image_path", "")
    if not image_path or not Path(image_path).exists():
        print(json.dumps({"success": False, "error": f"Image not found: {image_path}"}))
        return 1

    try:
        if payload.get("stream"):
            stream_chat_response(payload)
        else:
            response = build_chat_response(payload)
            print(json.dumps(response, ensure_ascii=False))
    except FileNotFoundError as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 1
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"Detection chat failed: {exc}"}))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
