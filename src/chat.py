import json
import asyncio
import os
from src.api import chat_openai_compatible
from typing import Optional, Iterable, Any, cast, Callable, Coroutine, Union, TypeVar
from openai import NOT_GIVEN, NotGiven
from openai.types import ReasoningEffort
from pathlib import Path

from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam, ChatCompletionToolMessageParam
from src.utils import MessageList, build_vision_messages
from src.api.interface_litellm import AsyncLiteLLM, LiteLLMConfig

# Global semaphore to control concurrent API calls
# Default limit: 10 concurrent calls, can be adjusted as needed
_api_semaphore = asyncio.Semaphore(400)

def _remove_thinking_process(response: str) -> str:
    """
    Remove thinking process from response if it exists.
    DeepSeek models (like deepseek-v3.2-speciale) sometimes return responses
    with thinking process marked by </think> tag. This function extracts only
    the content after </think>.
    
    Args:
        response: The raw response from the model
        
    Returns:
        The response with thinking process removed (content after </think>)
        or the original response if no </think> tag found
    """
    if "</think>" in response:
        # Split by </think> and return everything after it
        parts = response.split("</think>", 1)
        if len(parts) > 1:
            return parts[1].strip()
    return response

def _parse_model_and_provider(model: str) -> tuple[str, str]:
    """
    Parse model string to extract provider and model name.
    Format: provider@model_name or just model_name (defaults to openai-comp)
    
    Args:
        model: Model string, either "model_name" or "provider@model_name"
        
    Returns:
        Tuple of (actual_model_name, api_provider)
    """
    if "@" in model:
        provider, actual_model = model.split("@", 1)
        return actual_model, provider
    else:
        return model, "openai-comp"

async def direct_chat(
    model: str, 
    messages: Union[list[dict[str, Any]], MessageList],
    image_paths: Optional[list[Union[str, Path]]] = None,
    record_full_api_path: Optional[str] = None,
    temperature: Optional[float] | NotGiven = NOT_GIVEN,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    max_retries: int = 50,
    preview: bool = True,  # Whether to use preview mode with litellm
    build_message: bool = True,  # Whether to build vision messages
) -> str:
    # 实验性功能：使用 litellm 统一接口
    if preview:
        # 构建包含图片的消息列表
        if build_message:
            vision_messages = build_vision_messages(messages, image_paths)
        else:
            vision_messages = messages
        
        # 解析模型字符串
        actual_model = model
        
        # 配置 LiteLLM
        config = LiteLLMConfig(
            model=actual_model,
            temperature=temperature if temperature is not NOT_GIVEN else None,
            max_tokens=max_tokens,
            timeout=timeout,
            retries=max_retries,
        )
        
        # 获取 API 配置
        if "gemini" in actual_model.lower():
            litellm_base_url = os.getenv("GEMINI_BASE_URL")
            litellm_api_key = os.getenv("GEMINI_API_KEY")
        else:
            litellm_base_url = os.getenv("LITELLM_BASE_URL")
            litellm_api_key = os.getenv("LITELLM_API_KEY")
        
        # 根据模型类型调整 API base URL
        if litellm_base_url:
            if "gemini" in actual_model.lower():
                api_base = f"{litellm_base_url}/v1beta"
            else:
                api_base = f"{litellm_base_url}/v1"
        else:
            raise ValueError("LITELLM_BASE_URL environment variable is not set.")
        
        # 创建 LiteLLM 实例并调用
        llm = AsyncLiteLLM(
            model_config=config,
            api_base=api_base,
            api_key=litellm_api_key
        )
        
        result = await llm.chat(messages=vision_messages)
        
        # 如果需要记录完整的 API 路径
        if record_full_api_path:
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(record_full_api_path), exist_ok=True)
            with open(record_full_api_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps({
                    "model": actual_model,
                    "messages": vision_messages,
                    "response": result,
                    "provider": "litellm"
                }, ensure_ascii=False) + '\n')
        
        # Remove thinking process if exists (e.g., from DeepSeek models)
        return _remove_thinking_process(result)
        
    # 原有逻辑：使用现有的 API 接口
    async with _api_semaphore:
        # TODO: create a abstract class for all chat APIs
        # Parse model string to extract provider and actual model name
        actual_model, api_provider = _parse_model_and_provider(model)
        if "gemini" in model:
            gemini_system_instruction = None
            gemini_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    gemini_system_instruction = msg["content"]
                elif msg["role"] == "user":
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{"text": msg["content"]}]
                    })
                elif msg["role"] == "assistant":
                    gemini_messages.append({
                        "role": "model",
                        "parts": [{"text": msg["content"]}]
                    })
                else:
                    raise ValueError(f"Unsupported role: {msg['role']}")
            res = await chat_gemini_2_5(
                model=actual_model,
                system_instruction=gemini_system_instruction,
                messages=gemini_messages,
                record_full_api_path=record_full_api_path,
                temperature=temperature,
                max_retries=max_retries
            )
            # Remove thinking process if exists (e.g., from DeepSeek models)
            return _remove_thinking_process(res)
        if actual_model.startswith("o"):
            reasoning_effort = "high"
        else:
            reasoning_effort = None
        res = await chat_openai_compatible(
            model=actual_model,
            messages=cast(list[ChatCompletionMessageParam], messages),
            record_full_api_path=record_full_api_path,
            temperature=temperature,
            max_retries=max_retries,
            reasoning_effort=reasoning_effort,
            api_provider=api_provider,
        )
        # Remove thinking process if exists (e.g., from DeepSeek models)
        return _remove_thinking_process(res.content or "")


T = TypeVar('T')

async def safe_chat(model: str, messages: Union[list[dict[str, Any]], MessageList], 
            image_paths: Optional[list[Union[str, Path]]] = None,
            record_full_api_path: Optional[str] = None,
            temperature: Optional[float] | NotGiven = NOT_GIVEN,
            max_retries: int = 3,
            validator: Optional[Callable[[str], bool]] = None,
            formatter: Optional[Callable[[str], T]] = None,
            debug: bool = False
            ) -> Union[T, str]:
    cnt = 0
    while True:
        cnt += 1
        if cnt > max_retries:
            return "\\boxed{ Failed to response}\nCorrect" if formatter is None else formatter("\\boxed{ Failed to response}\nCorrect")
        res = await direct_chat(
            model=model,
            messages=messages,
            image_paths=image_paths,
            record_full_api_path=record_full_api_path,
            temperature=temperature,
            max_retries=max_retries,
        )
        if validator is None or validator(res):
            return res if formatter is None else formatter(res)
        if debug:
            print(f"Warning: Failed to validate response, retrying...", flush=True)
            print(res, flush=True)
