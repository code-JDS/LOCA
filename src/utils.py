import os
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, TypeAlias, TypedDict, Any, Callable, Optional, Awaitable, Union

Problem: TypeAlias = dict[Literal["id", "questions", "figure_paths"], str | list[str]]
ProblemSet: TypeAlias = list[Problem]
class ProblemWithAnswer(TypedDict):
    id: str
    questions: str
    solutions: str
    final_answers: list[str]
    figure_paths: Optional[list[str]]
ProblemSetWithAnswer: TypeAlias = list[ProblemWithAnswer]
def extract_problem(pwa: ProblemWithAnswer) -> Problem:
    result = {
        "id": pwa["id"],
        "questions": pwa["questions"],
        "solutions": pwa["solutions"],
        "final_answers": pwa["final_answers"],
        "figure_paths": pwa.get("figure_paths", None),
    }
    # Pass through sub-problem fields if present
    if "pre_context" in pwa:
        result["pre_context"] = pwa["pre_context"]
    if "sub_problems" in pwa:
        result["sub_problems"] = pwa["sub_problems"]
    return result

class Message(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str
class MessageList(list[Message]):
    def replace(self, replacements: dict[str, Any]) -> "MessageList":
        """
        Replace placeholders in the prompt with actual values.
        """
        new_prompt = MessageList()
        for i in range(len(self)):
            new_prompt.append(self[i].copy())
            for key, value in replacements.items():
                new_prompt[i]["content"] = new_prompt[i]["content"].replace(f"{{{key}}}", str(value))
        return new_prompt


@dataclass
class Instruction:
    """LLM instruction package with validation and formatting"""
    text: str
    validator: Callable[[str], bool]
    formatter: Callable[[str], Any]
    post_processor: Optional[Union[Callable[[Any], Any], Callable[[Any], Awaitable[Any]]]] = None


def load_prompt(file_path: str) -> MessageList:
    """
    Load a prompt file and return a list of dictionaries.
    """
    if not file_path.endswith('.json'):
        raise ValueError("File path must end with .json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = MessageList(json.load(f))
    return data


def load_jsonl(file_path: str) -> ProblemSetWithAnswer:
    """
    Load a JSONL file and return a list of dictionaries.
    """
    if not file_path.endswith('.jsonl'):
        raise ValueError("File path must end with .jsonl")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist")
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    return data

def sha256_hash(text: str | None) -> str:
    """
    Generate a SHA-256 hash of the given text.
    """
    return hashlib.sha256((text or "None").encode('utf-8')).hexdigest()

def bold_stdout(text: str) -> str:
    """
    Bold the given text for standard output.
    """
    return f"\033[1m{text}\033[0m"


def load_ref_sol(path: str, task_id: str) -> str:
    try:
        with open(path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("id") == task_id or data.get("id") == task_id.replace("_", "/"):
                        solution = data.get("llm_solution_v1", "")
                        if solution:
                            return solution
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"No matching entry found for task_id: {task_id}")
    except Exception as e:
        raise ValueError(f"Error loading fixed plan: {str(e)}")

def validate_plan_steps(plans: list[dict[str, Any]]):
    if not plans:
        return
    
    steps = sorted(plan["step_id"] for plan in plans)
    expected_steps = list(range(1, len(steps) + 1))
    
    if steps != expected_steps:
        error_msg = (
            f"Invalid step sequence: expected {expected_steps}, got {steps}\n"
            f"Full plan: {json.dumps(plans, indent=2, ensure_ascii=False)}"
        )
        raise ValueError(error_msg)


def create_aux_dir(aux_dir: str, problem_id: str) -> str | None:
    output_aux_path = os.path.join(aux_dir, problem_id) if aux_dir else None
    if output_aux_path and not os.path.exists(output_aux_path):
        os.makedirs(output_aux_path, exist_ok=True)
    return output_aux_path


def encode_image_to_base64(image_path: Union[str, Path]) -> str:
    """
    将图片文件编码为 base64 字符串
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        base64 编码的图片字符串
    """
    import base64
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def build_vision_messages(
    messages: Union[list[dict[str, Any]], MessageList],
    image_paths: Optional[list[Union[str, Path]]] = None
) -> Union[list[dict[str, Any]], MessageList]:
    """
    构建包含图片的多模态消息列表
    
    该函数将图片路径列表转换为符合多模态模型输入要求的消息格式。
    图片会被追加到最后一个 "user" 角色的消息内容中。
    
    Args:
        messages: 原始消息列表，每个消息包含 role 和 content 字段
        image_paths: 可选的图片路径列表
        
    Returns:
        包含图片信息的新消息列表，其中最后一个 user 消息的 content 
        从字符串转换为包含文本和图片的列表格式
        
    Example:
        >>> messages = [
        ...     {"role": "system", "content": "You are a helpful assistant."},
        ...     {"role": "user", "content": "What's in this image?"}
        ... ]
        >>> image_paths = ["path/to/image.png"]
        >>> result = build_vision_messages(messages, image_paths)
        >>> # result 的最后一个 user 消息的 content 将变为:
        >>> # [
        >>> #     {"type": "text", "text": "What's in this image?"},
        >>> #     {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        >>> # ]
    """
    if image_paths is None or len(image_paths) == 0:
        return messages
    
    # 深拷贝消息列表以避免修改原始数据
    new_messages = []
    for msg in messages:
        new_messages.append(msg.copy())
    
    # 找到最后一个 user 角色的消息
    last_user_idx = None
    for i in range(len(new_messages) - 1, -1, -1):
        if new_messages[i]["role"] == "user":
            last_user_idx = i
            break
    
    if last_user_idx is None:
        raise ValueError("No user message found in the message list to attach images to")
    
    # 获取最后一个 user 消息的文本内容
    last_user_msg = new_messages[last_user_idx]
    text_content = last_user_msg["content"]
    
    # 构建新的 content 列表，包含文本和图片
    content_list: list[dict[str, Any]] = [{"type": "text", "text": text_content}]
    
    # 添加所有图片
    for image_path in image_paths:
        # 编码图片为 base64
        base64_image = encode_image_to_base64(image_path)
        
        # 获取图片扩展名以确定 MIME 类型
        ext = Path(image_path).suffix.lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }.get(ext, 'image/png')
        
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{base64_image}"
            }
        })
    
    # 更新最后一个 user 消息的 content
    new_messages[last_user_idx]["content"] = content_list
    
    return new_messages
