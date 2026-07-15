from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from strawberry_pipeline.examples import build_qwen_pipeline
from strawberry_pipeline.qwen_client import QwenChatClient, QwenClientError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start an interactive Qwen chat about the current strawberry state.")
    parser.add_argument("--image-id", default="chat_qwen_image_001", help="Logical image id for this chat session.")
    parser.add_argument("--plot-id", default="plot_demo", help="Plot id used for memory retrieval.")
    parser.add_argument("--plant-batch-id", default="batch_demo", help="Plant batch id used for memory retrieval.")
    parser.add_argument(
        "--storage-path",
        default="memory/qwen_demo_memory.jsonl",
        help="Path to the JSONL memory file.",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Print the structured strawberry snapshot before entering chat mode.",
    )
    return parser.parse_args()


def build_system_prompt(context: dict) -> str:
    return (
        "You are a strawberry agricultural consultant. "
        "The user will ask follow-up questions about the current strawberry situation. "
        "Answer conversationally in Chinese, but stay grounded in the structured context provided below. "
        "If the user asks about maturity, harvest, lighting, risks, or next actions, use the context directly. "
        "If the context is uncertain, say so clearly. "
        "Do not invent sensor readings or new detections beyond the provided context.\n\n"
        "Current strawberry context:\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def build_context_payload(result) -> dict:
    return {
        "perception": asdict(result.perception),
        "diagnosis": asdict(result.diagnosis),
        "decision": asdict(result.decision),
        "history_count": len(result.history),
        "history": [
            {
                "image_id": record.image_id,
                "timestamp": record.timestamp,
                "diagnosis": asdict(record.diagnosis),
                "decision": asdict(record.decision),
                "metadata": record.metadata,
            }
            for record in result.history
        ],
    }


def print_banner() -> None:
    print("Qwen 草莓咨询对话已启动。")
    print("输入你的问题后回车即可，例如：现在适合采摘吗？")
    print("输入 /context 查看当前上下文，输入 /exit 结束对话。")


def main() -> None:
    args = parse_args()
    client = QwenChatClient.from_env()
    pipeline = build_qwen_pipeline(client=client, storage_path=Path(args.storage_path))
    result = pipeline.run(
        image="mock_image_for_qwen_chat",
        metadata={
            "image_id": args.image_id,
            "plot_id": args.plot_id,
            "plant_batch_id": args.plant_batch_id,
        },
    )
    context = build_context_payload(result)
    if args.show_context:
        print(json.dumps(context, ensure_ascii=False, indent=2))

    messages: list[dict[str, str]] = [{"role": "system", "content": build_system_prompt(context)}]
    print_banner()

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n结束对话。")
            break

        if not user_input:
            continue
        if user_input in {"/exit", "exit", "quit"}:
            print("结束对话。")
            break
        if user_input == "/context":
            print(json.dumps(context, ensure_ascii=False, indent=2))
            continue

        messages.append({"role": "user", "content": user_input})
        try:
            reply = client.chat(messages=messages)
        except QwenClientError as exc:
            print(f"\nQwen 调用失败: {exc}")
            continue

        messages.append({"role": "assistant", "content": reply})
        print(f"\nQwen: {reply}")


if __name__ == "__main__":
    main()
