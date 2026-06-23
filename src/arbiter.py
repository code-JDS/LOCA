import os
import json
from typing import List, Dict, Any
from src import ROOT_DIR, load_prompt
from src.chat import direct_chat

PROMPT_ARBITER = load_prompt(os.path.join(ROOT_DIR, "src/prompt/arbiter_prompt.json"))
PROMPT_SEMANTIC_VOTING = load_prompt(os.path.join(ROOT_DIR, "src/prompt/arbiter_semantic_voting.json"))

DEFAULT_MODEL = "deepseek-r1"

async def arbiter_for_voting(
    task_id: str,
    problem_statement: str,
    candidate_solutions: List[Dict[str, str]],
    model: str = None,
    temperature: float = 0.0,
) -> str:
    """
    Arbiter function for voting among multiple candidate solutions.
    
    Args:
        task_id: Task identifier
        problem_statement: Original problem statement
        candidate_solutions: List of dictionaries containing 'solution' and 'final_answer' keys
        model: Model to use for arbitration
        temperature: Temperature for model generation
        
    Returns:
        The final answer selected by the arbiter
    """
    if model is None:
        model = DEFAULT_MODEL
    
    # Format candidate solutions for the prompt
    formatted_candidates = ""
    for i, candidate in enumerate(candidate_solutions, 1):
        formatted_candidates += f"## Candidate Solution {i}\n"
        formatted_candidates += f"**Solution:**\n{candidate['solution']}\n\n"
        formatted_candidates += f"**Final Answer:**\n{candidate['final_answer']}\n\n"
        formatted_candidates += "---\n\n"
    
    messages = PROMPT_ARBITER.replace({
        "problem_statement": problem_statement,
        "candidate_solutions": formatted_candidates.strip(),
        "num_candidates": str(len(candidate_solutions))
    })
    
    return await direct_chat(
        model=model,
        messages=messages,
        temperature=temperature
    )


async def arbiter_for_semantic_voting(
    task_id: str,
    problem_statement: str,
    formatted_solutions: List[str],
    model: str = None,
    temperature: float = 0.0,
) -> str:
    """
    Arbiter function for semantic voting among multiple formatted solutions.
    Uses LLM to group semantically equivalent solutions and perform majority voting.
    
    Args:
        task_id: Task identifier
        problem_statement: Original problem statement
        formatted_solutions: List of formatted solution strings
        model: Model to use for arbitration
        temperature: Temperature for model generation
        
    Returns:
        The final answer selected by semantic majority voting
    """
    import random
    
    if model is None:
        model = DEFAULT_MODEL
        
    if not formatted_solutions:
        raise ValueError("No formatted solutions provided for voting")
    
    if len(formatted_solutions) == 1:
        return formatted_solutions[0]
    
    # Format candidates for the prompt
    formatted_candidates = ""
    for i, solution in enumerate(formatted_solutions, 1):
        formatted_candidates += f"## Solution {i}\n{solution}\n\n---\n\n"
    
    # Use the loaded prompt template
    messages = PROMPT_SEMANTIC_VOTING.replace({
        "problem_statement": problem_statement,
        "formatted_candidates": formatted_candidates.strip(),
    })
    
    try:
        result = await direct_chat(
            model=model,
            messages=messages,
            temperature=temperature
        )
        
        # Check if LLM indicates no majority
        if "NO_MAJORITY" in result:
            selected_solution = random.choice(formatted_solutions)
            print(f"🎲 Task {task_id}: No semantic majority found by LLM, randomly selected from {len(formatted_solutions)} solutions", flush=True)
            return selected_solution
        else:
            print(f"📝 Task {task_id}: Semantic majority found by LLM", flush=True)
            return result
            
    except Exception as e:
        print(f"⚠️ Warning: LLM semantic voting failed for task {task_id}: {e}. Falling back to random selection.", flush=True)
        # Fallback to random selection
        selected_solution = random.choice(formatted_solutions)
        print(f"🎲 Task {task_id}: Random fallback selection from {len(formatted_solutions)} solutions", flush=True)
        return selected_solution
