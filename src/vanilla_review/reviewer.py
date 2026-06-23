import json
import os
import asyncio
import re
from typing import Optional, Any, Literal
from src import ROOT_DIR, RESULT_ROOT_DIR, load_prompt
from src.chat import direct_chat, safe_chat
from src.utils import Instruction, bold_stdout
from src.instructions import JudgeInstruction

PROMPT_SIMPLE_REVIEWER = load_prompt(os.path.join(ROOT_DIR, "src/vanilla_review/prompt/simple_reviewer_prompt.json"))
if not PROMPT_SIMPLE_REVIEWER:
    raise ValueError("Simple reviewer prompt file not found or empty. Please check the path and content of the prompt file.")

PROMPT_SIMPLE_REVIEWER_STEPWISE = load_prompt(os.path.join(ROOT_DIR, "src/vanilla_review/prompt/simple_reviewer_prompt_stepwise.json"))
if not PROMPT_SIMPLE_REVIEWER_STEPWISE:
    raise ValueError("Stepwise Simple reviewer prompt file not found or empty. Please check the path and content of the prompt file.")

print(bold_stdout("Simple reviewer prompt loaded successfully"))


async def simple_review_final_answer(
    task_id: str,
    question_statement: str,
    solution: str,
    model: str = None,
    temperature: float = 0.0,
    stepwise: bool = False,
    figure_paths: list[str] = None,
) -> dict[str, Any]:
    """
    Simple review of final answer correctness.
    
    Args:
        task_id: The unique identifier for the current task
        question_statement: The original physics problem statement
        solution: The complete solution to be reviewed
        model: The model to use for reviewing
        temperature: Temperature setting for the model
        stepwise: If True, review step by step
        figure_paths: Optional paths to figures
        
    Returns:
        dict: Contains 'answer' (str) and 'judge' (str) - same format as other reviewers
    """
    # If stepwise is False, use the original logic
    if not stepwise:
        # Replace placeholders in the prompt template
        messages = PROMPT_SIMPLE_REVIEWER.replace({
            "question_statement": question_statement,
            "solution": solution,
        })

        # Set up API call logging path
        record_full_api_path = os.path.join(
            os.path.join(RESULT_ROOT_DIR, ".api.origin"),
            "_".join([task_id, "simple_review", model]) + ".json"
        )

        # Make the API call with validation using JudgeInstruction
        result = await safe_chat(
            model=model,
            messages=messages,
            image_paths=figure_paths,
            record_full_api_path=record_full_api_path,
            temperature=temperature,
            validator=JudgeInstruction.validator,
            formatter=JudgeInstruction.formatter,
            debug=True,
        )

        return result
    
    # Stepwise review logic
    # Split solution by "### Step X" pattern
    step_pattern = r'(### Step \d+)'
    parts = re.split(step_pattern, solution)
    
    # Reconstruct steps: each step consists of the header and its content
    steps = []
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            steps.append(parts[i] + parts[i + 1])
        else:
            print(f"Warning: Last step header found without content in problem {task_id}.", flush=True)
            steps.append(parts[i])
    
    # Remove "### Final Answer" and everything after it from the last step
    if steps and "### Final Answer" in steps[-1]:
        final_answer_pos = steps[-1].find("### Final Answer")
        steps[-1] = steps[-1][:final_answer_pos].rstrip()
    
    # Initialize final review result
    final_review = {
        "judge": "Correct",
        "answer": ""
    }
    
    # Review each step
    for step_idx, current_step in enumerate(steps):
        # Build previous steps context
        previous_steps = "\n".join(steps[:step_idx]) if step_idx > 0 else "No previous steps. This is the first step."
        
        # Review current step
        prompt_template = PROMPT_SIMPLE_REVIEWER_STEPWISE
        messages = prompt_template.replace({
            "question_statement": question_statement,
            "previous_steps": previous_steps,
            "current_step": current_step,
        })
        
        record_full_api_path = os.path.join(
            os.path.join(RESULT_ROOT_DIR, ".api.origin"),
            "_".join([task_id, "simple_review_stepwise", f"step{step_idx + 1}", model]) + ".json"
        )
        
        step_result = await safe_chat(
            model=model,
            messages=messages,
            image_paths=figure_paths,
            record_full_api_path=record_full_api_path,
            temperature=temperature,
            validator=JudgeInstruction.validator,
            formatter=JudgeInstruction.formatter,
            debug=True,
        )
        
        # If this step has an error, accumulate the error information
        if step_result.get("judge") == "Wrong":
            # Update final review status to Wrong
            final_review["judge"] = "Wrong"
            # Append step error information to final answer
            final_review["answer"] += f"Errors occurred in Step {step_idx + 1}.\n" + step_result.get("answer", "") + "\n"
    
    # If all steps pass, set success message
    if final_review["judge"] == "Correct":
        final_review["answer"] = "All steps reviewed successfully. No errors found in the solution."
    
    return final_review
