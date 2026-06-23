import json
import os
import asyncio
import re
from typing import Optional, Any, Literal
from src import ROOT_DIR, RESULT_ROOT_DIR, load_prompt
from src.chat import direct_chat, safe_chat
from src.utils import Instruction, bold_stdout
from src.instructions import JudgeInstruction
from src.loca.utils.instructions import check_explanation_fidelity
# Import from the new vanilla_review module to maintain compatibility
from src.vanilla_review.reviewer import simple_review_final_answer

PROMPT_ADVANCED_ANSWER = load_prompt(os.path.join(ROOT_DIR, "src/loca/utils/prompt/reviewer_answer.json"))
if not PROMPT_ADVANCED_ANSWER:
    raise ValueError("Answer Reviewer prompt file not found or empty. Please check the path and content of the prompt file.")

PROMPT_ADVANCED_ANSWER_STEPWISE = load_prompt(os.path.join(ROOT_DIR, "src/loca/utils/prompt/reviewer_answer_stepwise.json"))
if not PROMPT_ADVANCED_ANSWER_STEPWISE:
    raise ValueError("Stepwise Answer Reviewer prompt file not found or empty. Please check the path and content of the prompt file.")

PROMPT_SIMPLE_REVIEWER = load_prompt(os.path.join(ROOT_DIR, "src/loca/utils/prompt/simple_reviewer_prompt.json"))
if not PROMPT_SIMPLE_REVIEWER:
    raise ValueError("Simple reviewer prompt file not found or empty. Please check the path and content of the prompt file.")


async def advanced_reviewer_answer(
    task_id: str,
    question_statement: str,
    image_explanation: str,
    solution: str,
    instructions: dict[str, Instruction],
    model: Optional[str] = None, 
    temperature: Optional[float] = None,
    stepwise: bool = False,
    explanation: Optional[str] = None,
    figure_paths: Optional[list[str]] = None,
    turns: Optional[int] = None,
) -> dict[str, Any]:
    if not model:
        raise ValueError("Model must be specified for advanced reviewer question.")
    
    if not image_explanation:
        image_explanation = "(No dedicated image interpretation is provided. You need to read the images directly (if the problem does involve images and they're available)."

    # If stepwise is False, use the original logic
    if not stepwise:
        prompt_template = PROMPT_ADVANCED_ANSWER

        messages_dict = {
            key: prompt_template.replace({
                "question_statement": question_statement,
                "image_explanation": image_explanation,
                "solution": solution,
                "instruction": instruction.text
            }) for key, instruction in instructions.items()
        }

        record_full_api_path_dict = {
            key: os.path.join(
                os.path.join(RESULT_ROOT_DIR, ".api.origin"),
                "_".join([task_id, "advanced_review", key, model, f"turn{turns}"]) + ".json"
            ) for key in messages_dict.keys()
        }

        result = dict(zip(
            messages_dict.keys(),
            await asyncio.gather(*[
                safe_chat(
                    model=model,
                    messages=messages_dict[key],
                    image_paths=figure_paths,
                    record_full_api_path=record_full_api_path_dict[key],
                    temperature=temperature,
                    validator=instructions[key].validator,
                    formatter=instructions[key].formatter,
                    debug=True,
                ) for key in messages_dict.keys()
            ])
        ))
        for key, value in result.items():
            if instructions[key].post_processor:
                result[key] = await instructions[key].post_processor(value)
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
    
    # Prepare explanation section for prompt
    explanation_section = ""
    if explanation:
        explanation_section = f"{explanation}"
    
    # Initialize result dictionary
    result = {}
    for key in instructions.keys():
        result[key] = {
            "judge": "Correct",
            "answer": ""
        }
    # Review each step
    for step_idx, current_step in enumerate(steps):
        # Build previous steps context
        previous_steps = "\n".join(steps[:step_idx]) if step_idx > 0 else "No previous steps. This is the first step."
        
        # Prepare messages for all instructions (for concurrent execution)
        messages_dict = {}
        record_full_api_path_dict = {}
        
        for key, instruction in instructions.items():
            prompt_template = PROMPT_ADVANCED_ANSWER_STEPWISE
            messages_dict[key] = prompt_template.replace({
                "problem_statement": question_statement,
                "explanation_section": explanation_section,
                "image_explanation": image_explanation,
                "previous_steps": previous_steps,
                "current_step": current_step,
                "instruction": instruction.text
            })
            
            record_full_api_path_dict[key] = os.path.join(
                os.path.join(RESULT_ROOT_DIR, ".api.origin"),
                "_".join([task_id, "advanced_review_stepwise", key, model, f"turn{turns}_step{step_idx + 1}"]) + ".json"
            )
        
        # Execute all instruction reviews concurrently
        step_results = dict(zip(
            messages_dict.keys(),
            await asyncio.gather(*[
                safe_chat(
                    model=model,
                    messages=messages_dict[key],
                    image_paths=figure_paths,
                    record_full_api_path=record_full_api_path_dict[key],
                    temperature=temperature,
                    validator=instructions[key].validator,
                    formatter=instructions[key].formatter,
                    debug=True,
                ) for key in messages_dict.keys()
            ])
        ))
        
        # Apply post-processors
        for key, value in step_results.items():
            if instructions[key].post_processor:
                step_results[key] = await instructions[key].post_processor(value)

        for key, step_result in step_results.items():
            if "\\boxed{ Failed}" in step_result.get("answer", ""):
                step_results[key]["judge"] = "Correct"
                step_results[key]["answer"] = f"Error occurred during reviewing turn {turns} Step {step_idx + 1}.\n"
        
        # Check if any instruction found an error
        for key, step_result in step_results.items():
            if step_result.get("judge", "Correct") == "Wrong":
                # Add step number to feedback
                step_results[key]["answer"] = f"Errors occurred in Step {step_idx + 1}.\n" + step_result.get("answer", "") + "\n"
                # # Return results with only this failed step
                # return step_results
                # Append to overall errors
                result[key]["judge"] = "Wrong"
                result[key]["answer"] += step_results[key]["answer"]
        
    # If all steps pass, return success for all instructions
    for key in instructions.keys():
        if result[key]["judge"] == "Correct":
            result[key]["answer"] = "All steps reviewed successfully with no errors found."
    return result


async def review_explanation(
    task_id: str,
    problem_statement: str,
    explanation: str,
    model: str,
    temperature: float = 0.0,
    image_explanation: Optional[str] = None,
    figure_paths: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """
    Review a problem interpretation/explanation to check if it's faithful to the original problem.
    
    Args:
        task_id: The unique identifier for the current task
        problem_statement: The original problem statement
        explanation: The generated interpretation to review
        model: The model to use for reviewing
        temperature: Temperature setting for the model
        image_explanation: Optional explanation of images/figures in the problem
        figure_paths: Optional paths to figures referenced in the problem
        
    Returns:
        tuple[bool, str]: (is_correct, feedback)
            - is_correct: True if explanation is faithful, False otherwise
            - feedback: Detailed feedback about any issues found
    """
    # Prepare image explanation section
    if not image_explanation:
        image_explanation_section = "(No dedicated image interpretation is provided. You need to read the images directly if the problem does involve images and they're available.)"
    else:
        image_explanation_section = image_explanation

    # Create a simple prompt for reviewing the explanation
    review_prompt = [
        {
            "role": "system",
            "content": check_explanation_fidelity.text
        },
        {
            "role": "user",
            "content": f"# Original Problem Statement\n{problem_statement}\n\n# Image Explanation Involved in the Problem\n{image_explanation_section}\n\n# Problem Interpretation to Review\n{explanation}\n\nPlease review whether this problem interpretation is completely faithful to the original problem statement and physically correct."
        }
    ]
    
    # Get review result
    review_result = await safe_chat(
        model=model,
        messages=review_prompt,
        image_paths=figure_paths,
        temperature=temperature,
        validator=check_explanation_fidelity.validator,
        formatter=check_explanation_fidelity.formatter,
        debug=True,
    )
    
    # Extract judgment and feedback
    is_correct = review_result.get("judge", "Wrong") == "Correct"
    feedback = review_result.get("answer", "No feedback provided")
    
    return is_correct, feedback
