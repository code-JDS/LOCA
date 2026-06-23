import os
import json
from src import ROOT_DIR, RESULT_ROOT_DIR, load_prompt
from src.chat import direct_chat

PROMPT_SECRETARY = load_prompt(os.path.join(ROOT_DIR, "src/prompt/secretary/prompt_secretary.json"))
PROMPT_SECRETARY_FINAL = load_prompt(os.path.join(ROOT_DIR, "src/prompt/secretary/prompt_secretary_final.json"))

DEFAULT_MODEL = "gemini-2.5-pro"

async def structured_secretary(
    task_id: str,
    detailed_solution: str,
    original_problem_statement: str = None,
    model: str = None,
    temperature: float = 0,
    is_final: bool = False
) -> str:
    if model is None:
        model = DEFAULT_MODEL
    messages = PROMPT_SECRETARY.replace({
        "detailed_solution": detailed_solution
    }) if not is_final else PROMPT_SECRETARY_FINAL.replace({
        "detailed_solution": detailed_solution,
        "original_problem_statement": original_problem_statement if original_problem_statement else ""
    })
    
    return await direct_chat(
        model=model,
        messages=messages,
        temperature=temperature
    )
