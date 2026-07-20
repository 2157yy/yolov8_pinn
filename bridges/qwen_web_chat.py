import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from strawberry_pipeline.qwen_client import QwenChatClient, QwenClientError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def normalize_messages(payload):
    messages = []
    raw = payload.get("messages")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    if not messages:
        msg = str(payload.get("message", "")).strip()
        if msg:
            messages.append({"role": "user", "content": msg})
    if not messages:
        raise ValueError("message is required")
    return messages


SYSTEM_PROMPT = (
    "你是一位草莓种植专家，为温室种植户提供草莓种植、病虫害防治、"
    "温室环境管理等方面的专业建议。请用中文回答，回答要专业、准确、实用。"
    "如果问题超出你的知识范围，请诚实说明，不要编造信息。"
)


def build_chat_response(payload):
    env_file = Path(str(payload.get("env_file") or PROJECT_ROOT / "qwen_demo.env"))
    load_env_file(env_file)
    client = QwenChatClient.from_env()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(normalize_messages(payload))
    reply = client.chat(messages=messages)
    return {"success": True, "reply": reply}


def _write_event(event):
    line = json.dumps(event, ensure_ascii=False) + "\n"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(line.encode("utf-8"))
    else:
        sys.stdout.write(line)
    sys.stdout.flush()


def stream_chat_response(payload):
    env_file = Path(str(payload.get("env_file") or PROJECT_ROOT / "qwen_demo.env"))
    load_env_file(env_file)
    client = QwenChatClient.from_env()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(normalize_messages(payload))

    _write_event({"type": "ready"})
    reply_parts = []
    reasoning_parts = []

    for chunk in client.chat_stream(
        messages=messages,
        extra_body={"thinking": {"type": "enabled"}, "reasoning_effort": "high"},
    ):
        if chunk.get("type") == "chunk":
            reasoning_content = str(chunk.get("reasoning_content") or "")
            content_delta = str(chunk.get("content_delta") or "")
            if reasoning_content:
                reasoning_parts.append(reasoning_content)
                _write_event({"type": "thinking", "delta": reasoning_content})
            if content_delta:
                reply_parts.append(content_delta)
                _write_event({"type": "answer", "delta": content_delta})
        if chunk.get("type") == "usage" and chunk.get("usage"):
            _write_event({"type": "usage", "usage": chunk["usage"]})

    _write_event({
        "type": "done",
        "reply": "".join(reply_parts),
        "reasoning": "".join(reasoning_parts),
    })


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"success": False, "error": "Empty stdin input"}))
        return 1
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        return 1
    try:
        if payload.get("stream"):
            stream_chat_response(payload)
        else:
            response = build_chat_response(payload)
            print(json.dumps(response, ensure_ascii=False))
    except (ValueError, QwenClientError) as e:
        print(json.dumps({"success": False, "error": str(e)}))
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Qwen bridge failed: {e}"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
