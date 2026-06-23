import os
from typing import Literal, Optional
import asyncio
import re
from src import ROOT_DIR, RESULT_ROOT_DIR, load_prompt
from src.chat import direct_chat
from src.arbiter import arbiter_for_voting
from src.secretary import structured_secretary

SINGLE_LLM_PROMPT_DIR = os.path.join(ROOT_DIR, "src/prompt/single_llm")
PROMPT = load_prompt(os.path.join(SINGLE_LLM_PROMPT_DIR, "prompt.json"))
PROMPT_ZERO_SHOT_COT = load_prompt(os.path.join(SINGLE_LLM_PROMPT_DIR, "prompt_zero_shot_cot.json"))
PROMPT_COT = load_prompt(os.path.join(SINGLE_LLM_PROMPT_DIR, "cot.json"))
PROMPT_FIX_HISTORY = load_prompt(
    os.path.join(SINGLE_LLM_PROMPT_DIR, "prompt_fix_history_answer.json")
)

MODEL_DEFAULT = "gemini/gemini-2.5-pro"

async def single_llm_solver(
    task_id: str,
    problem_statement: str,
    image_explanation: str,  # NOTE: Only compatible within the LOCA scheme
    model: str = None,
    temperature: float = None,
    history_answer: str = None,
    history_review: str = None,
    options: dict = None,
    figure_paths: list[str] = None,
) -> tuple[str, str]:
    if not model:
        model = MODEL_DEFAULT
    
    if options is None:
        options = {}

    voting_n = options.get("voting_n", 1)
    
    # CoT-SC: When voting_n > 1, use CoT prompt for multiple sampling and vote for the best answer
    if voting_n > 1:
        return await _cot_sc_solver(
            task_id=task_id,
            problem_statement=problem_statement,
            model=model,
            temperature=temperature,
            history_answer=history_answer,
            history_review=history_review,
            voting_n=voting_n,
            options=options,
            figure_paths=figure_paths,
        )
    
    zero_shot_cot = options.get("zero_shot_cot", False)
    cot = options.get("cot", False)

    if history_answer and history_review:
        messages = PROMPT_FIX_HISTORY.replace({
            "problem_statement": problem_statement,
            "history_answer": history_answer, "history_review": history_review,
        })
    else:
        if zero_shot_cot:
            messages = PROMPT_ZERO_SHOT_COT.replace({
                "problem_statement": problem_statement,
            })
        elif cot:
            messages = PROMPT_COT.replace({
                "problem_statement": problem_statement,
            })
        else:
            messages = PROMPT.replace({
                "problem_statement": problem_statement,
            })
            if image_explanation:
                # Append image explanation to the last user message
                if messages[-1]['role'] != 'user':
                    raise ValueError("For `single-LLM`, expect the last message to be from user to append image explanation.")
                messages[-1]['content'] += f"\nDetailed Interpretation of Images Encontered in the Problem:\n{image_explanation}"
    
    api_record_path = os.path.join(
        RESULT_ROOT_DIR, ".api.origin",
        f"{task_id}_single_llm_{model}.json"
    )
    
    result = await direct_chat(
        model=model,
        messages=messages,
        image_paths=figure_paths,
        record_full_api_path=api_record_path,
        temperature=temperature
    )
    
    # Apply structured formatting if structured_output is True
    structured_output = options.get("structured_output", False)
    formatted_result = None
    if structured_output:
        try:
            formatted_result = await structured_secretary(
                task_id=task_id,
                detailed_solution=result,
                original_problem_statement=problem_statement,
                model=model,
                temperature=temperature or 0.0,
                is_final=True
            )
            # result = result + "### Final Answer\n" + formatted_result
        except Exception as e:
            print(f"⚠️ Warning: Failed to apply structured formatting for task {task_id}: {e}", flush=True)
            # Continue with unformatted result if formatting fails
    
    os.makedirs(os.path.join(RESULT_ROOT_DIR, task_id), exist_ok=True)
    with open(os.path.join(RESULT_ROOT_DIR, task_id, "single_llm_solution.md"), "w") as f:
        f.write(result)
    
    return result, formatted_result


def extract_final_answer(improved_solution: str) -> Optional[str]:

    pattern_final = r'(?s)Final Answer[:\s]*(.*)$'
    matches_final = re.findall(pattern_final, improved_solution, re.IGNORECASE | re.MULTILINE)
    
    if not matches_final:
        return None

    content_after_final = matches_final[-1]

    pattern_bracket = r'(?s)\[(.*?)\]'
    matches_bracket = re.findall(pattern_bracket, content_after_final)
    
    if matches_bracket:
        return matches_bracket[-1].strip()
    else:
        return content_after_final.strip()


async def _cot_sc_solver(
    task_id: str,
    problem_statement: str,
    model: str,
    temperature: float = None,
    history_answer: str = None,
    history_review: str = None,
    voting_n: int = 5,
    options: dict = None,
    figure_paths: list[str] = None,
) -> tuple[str, str]:
    if history_answer and history_review:
        messages = PROMPT_FIX_HISTORY.replace({
            "problem_statement": problem_statement,
            "history_answer": history_answer, 
            "history_review": history_review,
        })
    else:
        messages = PROMPT_COT.replace({
            "problem_statement": problem_statement,
        })
    
    model_lower = model.lower()
    needs_sequential = "gemini" in model_lower or "r1" in model_lower
    
    if needs_sequential:
        candidate_results = []
        for i in range(voting_n):
            result = await direct_chat(
                model=model,
                messages=messages,
                image_paths=figure_paths,
                temperature=temperature
            )
            candidate_results.append(result)
    else:
        tasks = []
        for i in range(voting_n):
            task = direct_chat(
                model=model,
                messages=messages,
                image_paths=figure_paths,
                temperature=temperature
            )
            tasks.append(task)
        
        candidate_results = await asyncio.gather(*tasks)
    
    candidate_solutions = []
    for result in candidate_results:
        candidate_solutions.append({
            "solution": result,
            "final_answer": extract_final_answer(result),
        })
    
    final_result = await arbiter_for_voting(
        task_id=task_id,
        problem_statement=problem_statement,
        candidate_solutions=candidate_solutions,
        model=model,
        temperature=0.0,
    )
    
    # Apply structured formatting if structured_output is True
    if options is None:
        options = {}
    structured_output = options.get("structured_output", False)
    formatted_result = None
    if structured_output:
        try:
            formatted_result = await structured_secretary(
                task_id=task_id,
                detailed_solution=final_result,
                original_problem_statement=problem_statement,
                model=model,
                temperature=temperature or 0.0,
                is_final=True
            )
            # final_result = final_result + "### Final Answer\n" + formatted_result
        except Exception as e:
            print(f"⚠️ Warning: Failed to apply structured formatting for CoT-SC task {task_id}: {e}", flush=True)
            # Continue with unformatted result if formatting fails
    
    return final_result, formatted_result
