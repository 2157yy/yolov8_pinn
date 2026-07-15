from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from run_qwen_chat import build_context_payload, build_system_prompt
from strawberry_pipeline.examples import build_qwen_pipeline
from strawberry_pipeline.qwen_client import QwenChatClient, QwenClientError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / "qwen_demo.env"
DEFAULT_STORAGE_PATH = PROJECT_ROOT / "memory" / "qwen_demo_memory.jsonl"
ALLOWED_ROLES = {"user", "assistant"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def normalize_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    raw_messages = payload.get("messages")
    if isinstance(raw_messages, list):
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role in ALLOWED_ROLES and content:
                messages.append({"role": role, "content": content})

    if not messages:
        single_message = str(payload.get("message", "")).strip()
        if single_message:
            messages.append({"role": "user", "content": single_message})

    if not messages:
        raise ValueError("message is required")

    return messages


def build_chat_response(payload: dict[str, Any]) -> dict[str, Any]:
    env_file = Path(str(payload.get("env_file") or DEFAULT_ENV_FILE))
    storage_path = Path(str(payload.get("storage_path") or DEFAULT_STORAGE_PATH))
    load_env_file(env_file)

    client = QwenChatClient.from_env()
    pipeline = build_qwen_pipeline(client=client, storage_path=storage_path)
    metadata = {
      "image_id": str(payload.get("image_id") or "web_qwen_image_001"),
      "plot_id": str(payload.get("plot_id") or "plot_demo"),
      "plant_batch_id": str(payload.get("plant_batch_id") or "batch_demo"),
    }
    result = pipeline.run(
        image="web_qwen_chat",
        metadata=metadata,
    )
    context = build_context_payload(result)
    conversation = [{"role": "system", "content": build_system_prompt(context)}]
    conversation.extend(normalize_messages(payload))
    reply = client.chat(messages=conversation)

    decision = context.get("decision", {})
    diagnosis = context.get("diagnosis", {})
    return {
        "success": True,
        "reply": reply,
        "context": context,
        "context_summary": {
            "decision_message": decision.get("message", ""),
            "harvest": decision.get("harvest"),
            "fill_light": decision.get("fill_light"),
            "manual_review": decision.get("manual_review"),
            "confidence_score": diagnosis.get("confidence_score"),
            "history_count": context.get("history_count", 0),
        },
    }


def _write_stream_event(event: dict[str, Any]) -> None:
    payload = json.dumps(event, ensure_ascii=False) + "\n"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(payload.encode("utf-8"))
    else:
        sys.stdout.write(payload)
    sys.stdout.flush()


def stream_chat_response(payload: dict[str, Any]) -> None:
    env_file = Path(str(payload.get("env_file") or DEFAULT_ENV_FILE))
    storage_path = Path(str(payload.get("storage_path") or DEFAULT_STORAGE_PATH))
    load_env_file(env_file)

    client = QwenChatClient.from_env()
    pipeline = build_qwen_pipeline(client=client, storage_path=storage_path)
    metadata = {
        "image_id": str(payload.get("image_id") or "web_qwen_image_001"),
        "plot_id": str(payload.get("plot_id") or "plot_demo"),
        "plant_batch_id": str(payload.get("plant_batch_id") or "batch_demo"),
    }
    result = pipeline.run(
        image="web_qwen_chat",
        metadata=metadata,
    )
    context = build_context_payload(result)
    summary = {
        "decision_message": context.get("decision", {}).get("message", ""),
        "harvest": context.get("decision", {}).get("harvest"),
        "fill_light": context.get("decision", {}).get("fill_light"),
        "manual_review": context.get("decision", {}).get("manual_review"),
        "confidence_score": context.get("diagnosis", {}).get("confidence_score"),
        "history_count": context.get("history_count", 0),
    }
    conversation = [{"role": "system", "content": build_system_prompt(context)}]
    conversation.extend(normalize_messages(payload))

    _write_stream_event({"type": "ready", "context_summary": summary})
    reply_parts: list[str] = []
    reasoning_parts: list[str] = []

    for chunk in client.chat_stream(
        messages=conversation,
        extra_body={"enable_thinking": True},
    ):
        if chunk.get("type") == "chunk":
            reasoning_delta = str(chunk.get("reasoning_delta") or "")
            content_delta = str(chunk.get("content_delta") or "")

            if reasoning_delta:
                reasoning_parts.append(reasoning_delta)
                _write_stream_event({"type": "thinking", "delta": reasoning_delta})

            if content_delta:
                reply_parts.append(content_delta)
                _write_stream_event({"type": "answer", "delta": content_delta})

        if chunk.get("type") == "usage" and chunk.get("usage"):
            _write_stream_event({"type": "usage", "usage": chunk["usage"]})

        if chunk.get("type") == "done":
            break

    _write_stream_event(
        {
            "type": "done",
            "reply": "".join(reply_parts),
            "reasoning": "".join(reasoning_parts),
            "context_summary": summary,
        }
    )


def read_request_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("request payload must be a JSON object")
    return parsed


def main() -> int:
    try:
        payload = read_request_payload()
        if payload.get("stream"):
            stream_chat_response(payload)
            return 0
        response = build_chat_response(payload)
    except (ValueError, QwenClientError) as exc:
        response = {"success": False, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive bridge handling
        response = {
            "success": False,
            "error": f"Unexpected Qwen bridge failure: {exc}",
        }

    output = json.dumps(response, ensure_ascii=False)
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(output.encode("utf-8"))
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
