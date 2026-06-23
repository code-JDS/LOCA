import os
from typing import Optional
from src import ROOT_DIR, RESULT_ROOT_DIR, load_prompt
from src.chat import direct_chat
from src.utils import bold_stdout


PROMPT_EXPLANATION = load_prompt(os.path.join(ROOT_DIR, "src/loca/utils/prompt/explanation.json"))
if not PROMPT_EXPLANATION:
    raise ValueError("Explanation prompt file not found or empty. Please check the path and content of the prompt file.")


async def generate_explanation(
    task_id: str,
    problem_statement: str,
    image_explanation: str,
    model: str,
    temperature: float = 0.0,
    feedback: Optional[str] = None,
    figure_paths: Optional[list[str]] = None,
) -> str:
    """
    Generate a detailed interpretation/explanation of the problem statement.
    
    Args:
        task_id: The unique identifier for the current task
        problem_statement: The physics problem statement to interpret
        image_explanation: Explanation of images/figures associated with the problem    
        model: The model to use for generating the explanation
        temperature: Temperature setting for the model
        feedback: Optional feedback from previous review to improve the explanation
        figure_paths: Optional paths to figures referenced in the problem
        
    Returns:
        str: The generated problem interpretation
    """
    # Prepare feedback section if feedback is provided
    if feedback is not None:
        feedback_section = f"## Previous Feedback\nThe previous interpretation had the following issues:\n{feedback}\n\nPlease address these issues in your new interpretation.\n\n"
    else:
        feedback_section = ""
    
    if not image_explanation:
        image_explanation = "(No dedicated image interpretation is provided. You need to read the image directly (if the problem does involve images and they're available)."
    
    # Create messages from template
    messages = PROMPT_EXPLANATION.replace({
        "problem_statement": problem_statement,
        "feedback_section": feedback_section,
        "image_explanation": image_explanation,
    })
    
    # Generate explanation
    explanation = await direct_chat(
        model=model,
        messages=messages,
        image_paths=figure_paths,
        temperature=temperature
    )
    
    return explanation.strip()
