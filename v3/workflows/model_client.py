"""model_client 包装器 — 提供 chat() 和 chat_json() 接口。

从 pipeline.model_client 导入并包装，使 chat() 返回 (text, usage) 元组。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pipeline.model_client import (
    LLMResponse,
    chat as _pipeline_chat,
)

logger = logging.getLogger(__name__)


def chat(prompt: str, **kwargs: Any) -> tuple[str, dict]:
    """发送 prompt 并返回 (text, usage) 元组。

    Args:
        prompt: 用户输入。
        **kwargs: 传递给 pipeline.model_client.chat() 的参数。

    Returns:
        (text, usage_dict) 元组，usage_dict 包含 prompt_tokens/completion_tokens/total_tokens。
    """
    resp: LLMResponse = _pipeline_chat(prompt, **kwargs)
    usage = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "total_tokens": resp.usage.total_tokens,
    }
    return resp.content, usage


def chat_json(prompt: str, **kwargs: Any) -> dict:
    """发送 prompt 并解析返回的 JSON。

    期望 LLM 返回纯 JSON 文本，解析后返回 dict。

    Args:
        prompt: 用户输入（应指示 LLM 返回 JSON）。
        **kwargs: 传递给 chat() 的参数。

    Returns:
        解析后的 dict。
    """
    text, _ = chat(prompt, **kwargs)
    text = text.strip()

    # 尝试提取 ```json ... ``` 代码块
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1])

    return json.loads(text)
