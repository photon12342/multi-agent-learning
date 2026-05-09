"""Unified LLM client supporting DeepSeek, Qwen, and OpenAI.

Provides a provider-agnostic interface via abstract base class,
with retry logic, token estimation, and cost calculation.
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

# Load .env from project root
_dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_dotenv_path)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Usage:
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""

    content: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    provider: str = ""


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "pricing": {"input": 0.27, "output": 1.10},
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-max",
        "api_key_env": "QWEN_API_KEY",
        "pricing": {"input": 0.80, "output": 2.40},
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "pricing": {"input": 0.15, "output": 0.60},
    },
}

DEFAULT_PROVIDER = "deepseek"
REQUEST_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0

# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse with generated content and usage stats.
        """

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count for a given text.

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """

    def calculate_cost(self, usage: Usage) -> float:
        """Calculate USD cost from usage stats.

        Args:
            usage: Token usage statistics.

        Returns:
            Cost in USD.
        """


# ---------------------------------------------------------------------------
# OpenAI-compatible provider
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider(LLMProvider):
    """LLM provider for any OpenAI-compatible API endpoint.

    Supports DeepSeek, Qwen, OpenAI, and any other service that exposes
    an OpenAI-compatible chat completions endpoint.
    """

    def __init__(self, provider_name: str = DEFAULT_PROVIDER) -> None:
        if provider_name not in PROVIDER_CONFIG:
            valid = list(PROVIDER_CONFIG)
            raise ValueError(f"Unknown provider '{provider_name}'. Valid: {valid}")

        config = PROVIDER_CONFIG[provider_name]
        api_key = os.environ.get(config["api_key_env"])

        if not api_key:
            logger.warning(
                "%s not set, using empty key", config["api_key_env"]
            )

        self.provider_name = provider_name
        self.base_url = config["base_url"].rstrip("/")
        self.model = config["model"]
        self.api_key = api_key or ""
        self.pricing = config["pricing"]

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )

        logger.info(
            "Initialized %s provider (model=%s, endpoint=%s)",
            provider_name,
            self.model,
            self.base_url,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            **kwargs: Overrides for model, temperature, max_tokens, etc.

        Returns:
            LLMResponse with generated content and usage stats.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            httpx.RequestError: On connection/timeout errors.
        """
        payload: dict[str, Any] = {
            "model": kwargs.pop("model", self.model),
            "messages": messages,
            **kwargs,
        }

        response = self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        content = choice["message"]["content"] or ""

        usage_data = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            usage=usage,
            model=data.get("model", self.model),
            provider=self.provider_name,
        )

    def count_tokens(self, text: str) -> int:
        """Estimate token count (4 chars per token rule-of-thumb).

        For production use, consider tiktoken or a provider-specific tokenizer.

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """
        if not text:
            return 0
        return len(text) // 4 + 1

    def calculate_cost(self, usage: Usage) -> float:
        """Calculate USD cost based on provider pricing.

        Args:
            usage: Token usage statistics.

        Returns:
            Cost in USD (rounded to 6 decimal places).
        """
        input_cost = (usage.prompt_tokens / 1_000_000) * self.pricing["input"]
        output_cost = (usage.completion_tokens / 1_000_000) * self.pricing["output"]
        return round(input_cost + output_cost, 6)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> OpenAICompatibleProvider:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


def chat_with_retry(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    max_retries: int = MAX_RETRIES,
    **kwargs: Any,
) -> LLMResponse:
    """Call provider.chat() with automatic retry and exponential backoff.

    Retries on HTTP 5xx, rate-limit (429), and network errors.

    Args:
        provider: An LLMProvider instance.
        messages: Chat messages.
        max_retries: Maximum number of retry attempts (default 3).
        **kwargs: Additional arguments passed to provider.chat().

    Returns:
        LLMResponse on success.

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            return provider.chat(messages, **kwargs)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (429,) or 500 <= status < 600:
                last_error = exc
                if attempt < max_retries:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "HTTP %d on attempt %d/%d, retrying in %.1fs",
                        status,
                        attempt,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
            else:
                raise
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < max_retries:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Request error on attempt %d/%d: %s, retrying in %.1fs",
                    attempt,
                    max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)

    raise RuntimeError(
        f"All {max_retries} retry attempts failed"
    ) from last_error


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def quick_chat(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    provider_name: str = DEFAULT_PROVIDER,
    **kwargs: Any,
) -> str:
    """Send a single prompt to the LLM and return the response content.

    Args:
        prompt: User message content.
        system_prompt: System message content.
        provider_name: Provider identifier (default: deepseek).
        **kwargs: Additional arguments passed to chat_with_retry().

    Returns:
        Response text content.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    with OpenAICompatibleProvider(provider_name=provider_name) as provider:
        response = chat_with_retry(provider, messages, **kwargs)
        return response.content


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    provider_name = os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER)
    logger.info("Using provider: %s", provider_name)

    # 1. 基础聊天
    resp = quick_chat("用一句话介绍你自己。", provider_name=provider_name)
    logger.info("快速聊天回复：%s", resp)

    # 2. 完整调用，带用量统计
    with OpenAICompatibleProvider(provider_name=provider_name) as provider:
        resp = chat_with_retry(
            provider,
            [
                {"role": "system", "content": "你是一位诗人。"},
                {
                    "role": "user",
                    "content": "用中文写一首关于 Python 的五言绝句。",
                },
            ],
        )
    logger.info("五言绝句：\n%s", resp.content)
    logger.info(
        "Token 用量：%d 输入 / %d 输出 / %d 总计",
        resp.usage.prompt_tokens,
        resp.usage.completion_tokens,
        resp.usage.total_tokens,
    )
    cost = provider.calculate_cost(resp.usage)
    logger.info("预估费用：$%.6f", cost)

    # 3. Token 估算
    sample = "你好世界，这是一条用于测试 Token 计数的消息。"
    estimated = provider.count_tokens(sample)
    logger.info("Token 估算：%r → %d tokens", sample, estimated)
