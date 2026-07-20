import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from strawberry_pipeline.qwen_client import QwenChatClient

DISEASE_NAMES = {
    0: "Angular Leafspot",
    1: "Anthracnose Fruit Rot",
    2: "Blossom Blight",
    3: "Gray Mold",
    4: "Leaf Spot",
    5: "Powdery Mildew Fruit",
    6: "Powdery Mildew Leaf",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def get_scene_info(image_path):
    img = cv2.imread(str(image_path))
    if img is None:
        return {"avg_light": 0.0, "time_period": "unknown"}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    avg_light = float(np.mean(gray) / 255.0)
    hour = datetime.now().hour
    if 6 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 17:
        period = "afternoon"
    elif 17 <= hour < 20:
        period = "evening"
    else:
        period = "night"
    return {"avg_light": round(avg_light, 4), "time_period": period}


def build_disease_system_prompt(detections, scene):
    if detections:
        lines = ["检测到以下草莓病害：", ""]
        for i, d in enumerate(detections, 1):
            lines.append(
                f"  {i}. {d['disease_name']} - 置信度 {d['confidence']:.2%}, "
                f"位置 bbox=[{d['bbox']['x1']:.0f}, {d['bbox']['y1']:.0f}, "
                f"{d['bbox']['x2']:.0f}, {d['bbox']['y2']:.0f}]"
            )
        lines.append("")
        lines.append(f"共检测到 {len(detections)} 处病害。")
    else:
        lines = ["未检测到已知草莓病害，植株表现健康。"]
    lines.append(f"场景光照均值: {scene.get('avg_light', 'N/A')}, 时段: {scene.get('time_period', 'N/A')}。")
    return (
        "你是一位草莓病害诊断专家。"
        "请根据以下YOLO实时检测结果，用中文回答用户关于草莓病害的问题。"
        "包括但不限于：病害识别、严重程度评估、成因分析、防治建议、是否需要人工复核。"
        "如果检测结果不确定或置信度较低，请诚实说明。"
        "不要编造检测结果中没有的病害信息。\n\n"
        "当前检测结果：\n"
        + "\n".join(lines)
    )


def run_detection(image_path, model_path, conf_threshold):
    model = YOLO(model_path)
    results = model.predict(source=str(image_path), conf=conf_threshold, verbose=False)
    result = results[0]

    detections = []
    if result.boxes is not None:
        boxes = result.boxes.xyxy
        classes = result.boxes.cls
        confs = result.boxes.conf
        for i in range(len(boxes)):
            cls_id = int(classes[i].item())
            conf = float(confs[i].item())
            x1, y1, x2, y2 = boxes[i].tolist()
            detections.append({
                "disease_class": cls_id,
                "disease_name": DISEASE_NAMES.get(cls_id, f"class_{cls_id}"),
                "confidence": round(conf, 4),
                "bbox": {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)},
            })

    return {"detections": detections, "detection_count": len(detections)}


def build_chat_response(payload):
    image_path = payload["image_path"]
    model_path = payload.get("model_path", "models/yolov8s-seg.pt")
    conf_threshold = float(payload.get("conf_threshold", 0.25))

    detection = run_detection(image_path, model_path, conf_threshold)
    scene = get_scene_info(image_path)

    client = QwenChatClient.from_env()
    system_prompt = build_disease_system_prompt(detection["detections"], scene)

    messages = [{"role": "system", "content": system_prompt}]
    history = payload.get("messages")
    if isinstance(history, list):
        for item in history:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role in ("user", "assistant") and content:
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
        "scene": scene,
    }


def _write_event(event):
    line = json.dumps(event, ensure_ascii=False) + "\n"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(line.encode("utf-8"))
    else:
        sys.stdout.write(line)
    sys.stdout.flush()


def stream_chat_response(payload):
    image_path = payload["image_path"]
    model_path = payload.get("model_path", "models/yolov8s-seg.pt")
    conf_threshold = float(payload.get("conf_threshold", 0.25))

    _write_event({"type": "status", "stage": "detecting", "message": "正在运行 YOLO 病害检测..."})
    detection = run_detection(image_path, model_path, conf_threshold)
    scene = get_scene_info(image_path)

    _write_event({
        "type": "ready",
        "detection_count": detection["detection_count"],
        "detections": detection["detections"],
        "scene": scene,
    })

    client = QwenChatClient.from_env()
    system_prompt = build_disease_system_prompt(detection["detections"], scene)

    messages = [{"role": "system", "content": system_prompt}]
    history = payload.get("messages")
    if isinstance(history, list):
        for item in history:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    if not any(m["role"] == "user" for m in messages):
        message = str(payload.get("message", "")).strip()
        if message:
            messages.append({"role": "user", "content": message})

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
        "detection_count": detection["detection_count"],
        "detections": detection["detections"],
        "scene": scene,
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
    except FileNotFoundError as e:
        print(json.dumps({"success": False, "error": str(e)}))
        return 1
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Detection chat failed: {e}"}))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
