"""
LiteLLM unified interface for multiple LLM providers
"""

import base64
import time
import asyncio
from pathlib import Path
from typing import Optional, Any, Dict, Union, override
from dataclasses import dataclass, asdict
import datetime
import random

from litellm import completion, acompletion
from .base import LLMInterface


TEMPERATURE_DEFAULT = 0.0
TOP_P_DEFAULT = None
MAX_TOKENS_DEFAULT = None
TIMEOUT_DEFAULT = None
RETRIES_DEFAULT = 16
RETRY_DELAY_DEFAULT = 10  # seconds


def get_time() -> str:
    return datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S.%f")


@dataclass
class LiteLLMConfig:
    """Configuration for LiteLLM interface
    
    API keys and base URLs are read from environment variables:
    - OPENAI_API_KEY, OPENAI_API_BASE
    - ANTHROPIC_API_KEY, ANTHROPIC_API_BASE
    - And other provider-specific environment variables
    
    Args:
        model: Model name (e.g., "gpt-4", "claude-3-5-sonnet-20241022", "gemini/gemini-pro")
        temperature: Sampling temperature (0.0 to 2.0)
        top_p: Nucleus sampling parameter
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
        retries: Number of retry attempts on failure
        retry_delay: Delay between retries in seconds
        extra_params: Additional parameters to pass to LiteLLM
    """
    model: str
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None
    retries: Optional[int] = None
    retry_delay: Optional[int] = None
    extra_params: Optional[Dict[str, Any]] = None

    def to_json(self) -> dict:
        return asdict(self)


class AsyncLiteLLM(LLMInterface):
    """Asynchronous LiteLLM interface"""
    
    config: LiteLLMConfig
    api_base: Optional[str]
    api_key: Optional[str]

    def __init__(self, model_config: LiteLLMConfig, api_base: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize AsyncLiteLLM interface
        
        Args:
            model_config: Model configuration
            api_base: Custom API base URL (optional, overrides environment variables)
            api_key: API key (optional, overrides environment variables)
        """
        self.config = model_config
        self.api_base = api_base
        self.api_key = api_key

        if self.config.retries is None:
            self.config.retries = RETRIES_DEFAULT
        if self.config.retry_delay is None:
            self.config.retry_delay = RETRY_DELAY_DEFAULT

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """生成文本响应（实现抽象基类方法）
        
        Args:
            prompt: 文本提示
            **kwargs: 额外的参数覆盖配置
            
        Returns:
            生成的文本响应
        """
        # 构建简单的用户消息
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages=messages, **kwargs)

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """调用 LiteLLM 进行对话生成
        
        Args:
            messages: 消息列表，每个消息包含 role 和 content 字段
                     content 可以是字符串或包含文本和图片的列表
            **kwargs: 额外的参数覆盖配置
            
        Returns:
            生成的文本响应
        """
        response = await self._chat_completion(messages=messages, **kwargs)
        
        # 提取响应内容
        if hasattr(response, 'choices') and len(response.choices) > 0:
            message = response.choices[0].message
            if hasattr(message, 'content') and message.content:
                return message.content
        
        # 如果无法获取有效内容，打印警告和传入大模型的信息(messages)，并返回失败标记
        print(f"Warning: Failed to get valid content from response", flush=True)
        print(f"Messages:\n---\n{messages}\n---\n", flush=True)
        return "\\boxed{ Failed}"

    async def _chat_completion(self, messages: list[dict[str, Any]], **kwargs: Any):
        """Internal method to call LiteLLM async completion
        
        Args:
            messages: List of message dictionaries
            **kwargs: Additional parameters to override config
            
        Returns:
            LiteLLM completion response
        """
        
        for attempt in range(self.config.retries):
            try:
                # Build request parameters
                params = {
                    "model": self.config.model,
                    "messages": messages,
                    "timeout": self.config.timeout if self.config.timeout is not None else TIMEOUT_DEFAULT,
                }
                
                # Add API base and key if provided
                if self.api_base is not None:
                    params["api_base"] = self.api_base
                if self.api_key is not None:
                    params["api_key"] = self.api_key
                
                # Add optional parameters from config (if not None)
                # Only add temperature if it's explicitly set and not the default value
                if not any(suffix in self.config.model.lower() for suffix in ["gpt", "o1", "o3", "o4"]):
                    params["temperature"] = self.config.temperature if self.config.temperature is not None else TEMPERATURE_DEFAULT
                # Only add top_p if it's explicitly set and not the default value
                if not any(suffix in self.config.model.lower() for suffix in ["gpt", "o1", "o3", "o4"]):
                    params["top_p"] = self.config.top_p if self.config.top_p is not None else TOP_P_DEFAULT
                params["max_tokens"] = self.config.max_tokens if self.config.max_tokens is not None else MAX_TOKENS_DEFAULT
                
                # Add extra parameters if specified
                if self.config.extra_params:
                    params.update(self.config.extra_params)

                # NOTE: if gemini is used, set thinkingBudget directly
                # if "gemini" in self.config.model.lower():
                #     if 'pro' in self.config.model.lower():
                #         # "thinkingBudget": 32768 (max)
                #         params["thinkingConfig"] = {"includeThoughts": True, "thinkingBudget": 8192}
                #     elif 'flash' in self.config.model.lower():
                #         # "thinkingBudget": 24576 (max)
                #         params["thinkingConfig"] = {"includeThoughts": True, "thinkingBudget": 8192}
                if "qwen3-235b-a22b" in self.config.model.lower():
                    params["enable_thinking"] = False
                
                # Override with kwargs
                params.update(kwargs)
                
                # Call LiteLLM async completion
                response = await acompletion(**params)
                return response
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}", flush=True)
                if attempt < self.config.retries - 1:
                    self.config.retry_delay = self.config.retry_delay if self.config.retry_delay is not None else RETRY_DELAY_DEFAULT
                    self.config.retry_delay += random.uniform(0, 5)  # Add jitter
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise e
