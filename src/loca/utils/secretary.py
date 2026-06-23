import os
import json
from src import ROOT_DIR, RESULT_ROOT_DIR, load_prompt
from src.chat import direct_chat
from src.utils import bold_stdout

PROMPT_SECRETARY_FOR_BUGS = load_prompt(os.path.join(ROOT_DIR, "src/loca/utils/prompt/secretary.json"))
if not PROMPT_SECRETARY_FOR_BUGS:
    raise ValueError("Secretary for bugs prompt file not found or empty. Please check the path and content of the prompt file.")

PROMPT_SECRETARY_FOR_BUGS_STEPWISE = load_prompt(os.path.join(ROOT_DIR, "src/loca/utils/prompt/secretary_stepwise.json"))
if not PROMPT_SECRETARY_FOR_BUGS_STEPWISE:
    raise ValueError("Stepwise Secretary for bugs prompt file not found or empty. Please check the path and content of the prompt file.")

PROMPT_EXPLANATION_SECRETARY = load_prompt(os.path.join(ROOT_DIR, "src/loca/utils/prompt/explanation_secretary.json"))
if not PROMPT_EXPLANATION_SECRETARY:
    raise ValueError("Explanation secretary prompt file not found or empty. Please check the path and content of the prompt file.")

async def secretary_for_bugs(
    task_id: str,
    detailed_review: str,
    model: str = None,
    temperature: float = 0,
    stepwise: bool = False,
    figure_paths: list[str] = None,
) -> str:
    if model is None:
        raise ValueError("Model must be specified for secretary_for_bugs")
    template = PROMPT_SECRETARY_FOR_BUGS_STEPWISE if stepwise else PROMPT_SECRETARY_FOR_BUGS
    messages = template.replace({
        "review": detailed_review
    })
    
    return await direct_chat(
        model=model,
        messages=messages,
        image_paths=figure_paths,
        temperature=temperature
    )


async def secretary_for_explanation_feedback(
    task_id: str,
    review_feedback: str,
    model: str = None,
    temperature: float = 0,
    figure_paths: list[str] = None,
) -> str:
    """
    Extract and organize key issues from explanation review feedback.
    
    Args:
        task_id: The unique identifier for the current task
        review_feedback: The feedback from explanation review
        model: The model to use for processing
        temperature: Temperature setting for the model
        figure_paths: Optional paths to figures
        
    Returns:
        str: Organized feedback with key issues extracted
    """
    if model is None:
        raise ValueError("Model must be specified for secretary_for_explanation_feedback")
    
    template = PROMPT_EXPLANATION_SECRETARY
    messages = template.replace({
        "review": review_feedback
    })
    
    return await direct_chat(
        model=model,
        messages=messages,
        image_paths=figure_paths,
        temperature=temperature
    )
