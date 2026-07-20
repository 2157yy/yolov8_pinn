from __future__ import annotations

import os
import json
import httpx
from typing import Any, Iterator

from dotenv import load_dotenv
load_dotenv()  #这个语句是自动找env的模型和密钥

class QwenClientError(Exception):
    pass
    
def extract_json_dict(text: str) -> dict[str, Any]:
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1 and start < end:
            try:
                result = json.loads(text[start:end+1])
            except json.JSONDecodeError:
                raise QwenClientError(f"JSON 截取后仍解析失败，原文本前100字符: {text[:100]}")
        else:
            raise QwenClientError(f"未找到 JSON 边界，原文本前100字符: {text[:100]}")
            
    if not isinstance(result, dict):
        raise QwenClientError(f"解析结果非 dict，实际类型为: {type(result).__name__}")
        
    return result


class QwenChatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
    ):
        # 去掉末尾斜杠
        self.base_url = base_url.rstrip("/")#自动去除末尾斜杠
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_env(cls) -> "QwenChatClient":
        base_url = os.getenv("QWEN_BASE_URL", "").strip()
        api_key = os.getenv("QWEN_API_KEY", "").strip()
        model = os.getenv("QWEN_MODEL", "").strip()
        if not (base_url and api_key and model):
            raise ValueError(
                "env环境设置错误"
            )
        return cls(base_url, api_key, model)
    

    @property
    def _chat_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"
    
    def _post(self, request_body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}", 
        }
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(self._chat_url, json=request_body, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise QwenClientError(
                f"HTTP {exc.response.status_code} 错误: {detail}"
            ) from exc
        except httpx.RequestError as exc:
            raise QwenClientError(f"网络请求失败: {exc}") from exc
        
    def chat(
        self,
        messages: list[dict[str, str]],
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        request_body = {
            "model": self.model,
            "messages": messages,
        }
        if extra_body:
            request_body.update(extra_body)

        data = self._post(request_body)

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise QwenClientError("响应格式无效，无法提取回复内容") from exc
                 
    def chat_stream(
        self,
        messages: list[dict[str, str]],
        extra_body: dict[str, Any] | None = None,
        enable_thinking: bool = False,
    ) -> Iterator[dict[str, Any]]:
        
        request_body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if enable_thinking :
            request_body["enable_thinking"] = True
        if extra_body:
            request_body.update(extra_body)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            with httpx.Client(timeout=30) as client:
                # 注意：这里是 client.stream("POST", url, ...)
                with client.stream("POST", self._chat_url, json=request_body, headers=headers) as resp:
                    resp.raise_for_status()
                
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                    
                        data_str = line[len("data:"):].strip()
                        if data_str == "[DONE]":
                            break
                    
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue  
                    
                        choices = chunk.get("choices", [])
                        content_delta = ""
                        reasoning_content = ""
                        finish_reason = None
                        if choices:
                            delta = choices[0].get("delta", {})
                            content_delta = delta.get("content", "")
                            reasoning_content = delta.get("reasoning_content", "")
                            finish_reason = choices[0].get("finish_reason")

                        
                        if content_delta or reasoning_content or finish_reason:
                            yield {
                                "type": "chunk",
                                "content_delta": content_delta,
                                "reasoning_content": reasoning_content,
                                "finish_reason": finish_reason,
                            }

        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise QwenClientError(f"HTTP {exc.response.status_code} 错误: {detail}") from exc
        except httpx.RequestError as exc:
            raise QwenClientError(f"网络请求失败: {exc}") from exc
        

if __name__ == "__main__":
    client = QwenChatClient.from_env()
    messages = [
        {"role": "system", "content": "你是一个农业专家，提供专业的农业知识和建议。能够分析温室大棚内的传感器数据，并根据数据提供科学的种植建议。"},
        {"role": "user", "content": "请根据现在的温湿度和光照强度数据，给出适合的种植建议。温度: 28°C, 湿度: 65%, 光照强度: 12000 lux。"},
    ]
    try:
        for event in client.chat_stream(
            messages,
            extra_body={"thinking": {"type": "enabled"}, "reasoning_effort": "high"},
        ):
            print(event)  
    except QwenClientError as e:
        print("出错:", e)
