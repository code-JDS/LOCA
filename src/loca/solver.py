import os
import json
import asyncio
from typing import Optional
import time

from src.loca.utils.reviewer import advanced_reviewer_answer, simple_review_final_answer, review_explanation
from src.loca.utils.augmentation import augment_origin_answer, simple_refiner
from src.loca.utils.secretary import secretary_for_bugs, secretary_for_explanation_feedback
from src.loca.utils.instructions import instruction_dict_answer
from src.loca.utils.explanation import generate_explanation
from src.secretary import structured_secretary


MODEL_DEFAULT = "gemini-2.5-pro"


async def loca_solver(
    task_id: str,
    question_statement: str,
    solution: str,
    image_explanation: str,
    output_aux_path: Optional[str] = None,
    augmentation_model: Optional[str] = None,
    review_model: Optional[str] = None,
    max_error_times: int = 5,
    target_times: int = 3,
    temperature: float = 0.0,
    ablation: bool = False,
    keep_aug: bool = False,
    keep_specific_verification: bool = False,
    n_interpretation: int = 0,
    stepwise_review: bool = False,
    figure_paths: Optional[list[str]] = None,
) -> tuple[bool, str, Optional[str]]:
    """
    LOCA solver: Iteratively improve a physics solution until it meets quality criteria.
    
    Args:
        task_id: The unique identifier for the current task
        question_statement: The physics question statement
        solution: The solution to augment and review
        output_aux_path: path of output aux file
        augmentation_model: The model to use for augmentation
        review_model: The model to use for reviewing
        max_error_times: Maximum number of allowed errors before failing
        target_times: Number of consecutive consistent results needed for success
        temperature: Temperature setting for the models
        ablation: If True, use simple self-refine approach; if False, use advanced multi-criteria review
        keep_aug: If True, keep augmentation
        keep_specific_verification: If True, keep specific verification steps in review
        
    Returns:
        tuple[bool, str, Optional[str]]:
            - success flag (True if solution passed review, False otherwise)
            - improved solution text or failure report
            - formatted solution text if formatting succeeded, else None
    """

    # Use default models if not specified
    if augmentation_model is None:
        augmentation_model = MODEL_DEFAULT
    if review_model is None:
        review_model = MODEL_DEFAULT

    # Initialize state variables
    bugs_report = "Initial state, no bugs report"
    error_count = 0
    consistent_count = 0
    turn = 0
    current_solution = solution
    formatted_solution = None
    problem_explanation = None

    # Check for existing state file to resume from breakpoint
    state_file_path = None
    if output_aux_path:
        state_file_path = os.path.join(output_aux_path, "state.json")
        if os.path.exists(state_file_path):
            try:
                with open(state_file_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                # Restore state from file
                turn = state.get("turn", 0)
                error_count = state.get("error_count", 0)
                consistent_count = state.get("consistent_count", 0)
                current_solution = state.get("solution", solution)
                bugs_report = state.get("bugs_report", "Initial state, no bugs report")
                formatted_solution = state.get("formatted_solution", None)
                problem_explanation = state.get("problem_explanation", None)
                
                print(f"Resuming task {task_id} from turn {turn + 1}, error_count={error_count}, consistent_count={consistent_count}", flush=True)
                
                # Check if already completed (whether failed or not)
                if consistent_count >= target_times:
                    print(f"✅ Task {task_id} already completed successfully in previous run", flush=True)
                    return True, current_solution, formatted_solution
                
                if error_count > max_error_times:
                    print(f"✅ Task {task_id} already completed (while failed in giving a consistent solution) in previous run", flush=True)
                    return False, current_solution, formatted_solution
                    
            except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
                print(f"⚠️ Warning: Could not restore state from {state_file_path}: {e}. Starting fresh.", flush=True)
                # Clean up corrupted state file
                if os.path.exists(state_file_path):
                    os.remove(state_file_path)
                # Reset to initial state if state file is corrupted
                bugs_report = "Initial state, no bugs report"
                error_count = 0
                consistent_count = 0
                turn = 0
                current_solution = solution
                formatted_solution = None
                problem_explanation = None

    def save_state():
        """Save current state to state file"""
        if state_file_path:
            state = {
                "turn": turn,
                "error_count": error_count,
                "consistent_count": consistent_count,
                "solution": current_solution,
                "bugs_report": bugs_report,
                "formatted_solution": formatted_solution,
                "problem_explanation": problem_explanation,
            }
            try:
                with open(state_file_path, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Could not save state to {state_file_path}: {e} at turn {turn}", flush=True)

    # Explanation-Review loop (if n_interpretation > 0)
    if n_interpretation > 0 and problem_explanation is None:        
        explanation_feedback = None
        for interp_iter in range(n_interpretation):
            # Generate explanation
            problem_explanation = await generate_explanation(
                task_id=task_id,
                problem_statement=question_statement,
                image_explanation=image_explanation,
                model=augmentation_model,
                temperature=temperature,
                feedback=explanation_feedback,
                figure_paths=figure_paths,
            )
            
            # Save explanation to aux file
            if output_aux_path is not None:
                explanation_file = os.path.join(output_aux_path, f"explanation_{interp_iter + 1}.md")
                with open(explanation_file, "w", encoding="utf-8") as f:
                    f.write(problem_explanation)
            
            # Review explanation (skip review on last iteration)
            if interp_iter < n_interpretation - 1:
                is_correct, explanation_feedback = await review_explanation(
                    task_id=task_id,
                    problem_statement=question_statement,
                    explanation=problem_explanation,
                    model=review_model,
                    temperature=temperature,
                    image_explanation=image_explanation,
                    figure_paths=figure_paths,
                )
                
                # Save review feedback to aux file
                if output_aux_path is not None:
                    review_file = os.path.join(output_aux_path, f"explanation_review_{interp_iter + 1}.md")
                    with open(review_file, "w", encoding="utf-8") as f:
                        f.write(f"# Explanation Review\n\n")
                        f.write(f"**Judgment**: {'Correct' if is_correct else 'Wrong'}\n\n")
                        f.write(f"**Feedback**:\n{explanation_feedback}\n")
                
                if is_correct:
                    break
                else:
                    # Process feedback through secretary to extract key issues
                    explanation_feedback = await secretary_for_explanation_feedback(
                        task_id=task_id,
                        review_feedback=explanation_feedback,
                        model=review_model,
                        temperature=temperature,
                        figure_paths=figure_paths,
                    )
                    
                    # Save processed feedback to aux file
                    if output_aux_path is not None:
                        processed_feedback_file = os.path.join(output_aux_path, f"explanation_feedback_{interp_iter + 1}.md")
                        with open(processed_feedback_file, "w", encoding="utf-8") as f:
                            f.write(f"# Processed Feedback for Next Iteration\n\n")
                            f.write(explanation_feedback)

    while True:
        turn += 1

        current_solution = await augment_origin_answer(
            task_id=task_id,
            question_statement=question_statement,
            image_explanation=image_explanation,
            solution=current_solution,
            bugs_report=bugs_report,
            aug_model=augmentation_model,
            temperature=temperature,
            turns=turn,
            explanation=problem_explanation,
            figure_paths=figure_paths,
        ) if ((not ablation) or keep_aug) else await simple_refiner(
            task_id=task_id,
            question_statement=question_statement,
            solution=current_solution,
            feedback=bugs_report,
            model=augmentation_model,
            temperature=temperature,
            turns=turn,
            figure_paths=figure_paths,
        )
        # Without actual bugs report, this is a retelling

        # If n_interpretation > 0, prepend explanation to solution
        if n_interpretation > 0 and problem_explanation is not None:
            pure_solution = current_solution
            current_solution = f"# Problem Explanation\n---\n{problem_explanation}\n\n# Solution\n---\n{current_solution}"

        if output_aux_path is not None and turn > 1:
            record_file_at_aux_path = os.path.join(output_aux_path, f"refined_answer_{turn}.md")
            with open(record_file_at_aux_path, "w", encoding="utf-8") as f:
                f.write(current_solution)

        # Determine the solution to review (pure_solution without explanation if n_interpretation > 0)
        solution_to_review = pure_solution if (n_interpretation > 0 and problem_explanation is not None) else current_solution
        
        # Check if stepwise review should be enabled
        use_stepwise = stepwise_review and ("### Step" in solution_to_review)
        
        review_dict = await advanced_reviewer_answer(
            task_id=task_id,
            question_statement=question_statement,
            image_explanation=image_explanation,
            solution=solution_to_review,
            instructions=instruction_dict_answer,
            model=review_model,
            temperature=temperature,
            stepwise=use_stepwise,
            explanation=problem_explanation if (n_interpretation > 0 and problem_explanation is not None) else None,
            figure_paths=figure_paths,
            turns=turn,
        ) if ((not ablation) or keep_specific_verification) else await simple_review_final_answer(
            task_id=task_id,
            question_statement=question_statement,
            solution=solution_to_review,
            model=review_model,
            temperature=temperature,
            stepwise=use_stepwise,
            figure_paths=figure_paths,
        )
        if ablation and (not keep_specific_verification):
            review_dict = {
                "Final Answer Review": review_dict
            }

        if output_aux_path is not None:
            # Save holistic review
            full_review_content = "# Solution Review\n"
            for key, review in review_dict.items():
                full_review_content += f"## {key}\n{review['answer']}\n"
                full_review_content += f"Judge: {review['judge']}\n\n"
            record_file_at_aux_path = os.path.join(output_aux_path, f"full_review_{turn}.md")
            with open(record_file_at_aux_path, "w", encoding="utf-8") as f:
                f.write(full_review_content)

        is_consistent = all([review["judge"] == "Correct" for review in review_dict.values()])

        if not is_consistent:
            final_review = "# Issues found in solution\n"
            for key, review in review_dict.items():
                if review["judge"] == "Wrong":
                    final_review += f"## {key}\n{review['answer']}\n"

            bugs_report = await secretary_for_bugs(
                    task_id=task_id,
                    detailed_review=final_review,
                    model=review_model,
                    temperature=temperature,
                    stepwise=stepwise_review,
                    figure_paths=figure_paths,
                    )

            if output_aux_path is not None:
                record_file_at_aux_path = os.path.join(output_aux_path, f"bugs_report_{turn}.md")
                with open(record_file_at_aux_path, "w", encoding="utf-8") as f:
                    f.write(bugs_report)

            consistent_count = 0
            error_count += 1

            if error_count > max_error_times:
                # Apply structured formatting
                try:
                    print(f"🔄 Applying structured formatting for task {task_id}...", flush=True)
                    formatted_solution = await structured_secretary(
                        task_id=task_id,
                        detailed_solution=current_solution,
                        original_problem_statement=question_statement,
                        model=review_model,
                        temperature=temperature,
                        is_final=True
                    )
                except Exception as e:
                    print(f"⚠️ Warning: Failed to apply structured formatting for task {task_id}: {e}", flush=True)
                    # Continue with unformatted solution if formatting fails

                # Save state before failing
                save_state()
                return False, current_solution, formatted_solution

        else:
            consistent_count += 1
            bugs_report = "No bugs found in the last review"

            if consistent_count == target_times:
                # Apply structured formatting
                try:
                    print(f"🔄 Applying structured formatting for task {task_id}...", flush=True)
                    formatted_solution = await structured_secretary(
                        task_id=task_id,
                        detailed_solution=current_solution,
                        original_problem_statement=question_statement,
                        model=review_model,
                        temperature=temperature,
                        is_final=True
                    )
                except Exception as e:
                    print(f"⚠️ Warning: Failed to apply structured formatting for task {task_id}: {e}", flush=True)
                    # Continue with unformatted solution if formatting fails
                
                # Save state before success
                save_state()
                return True, current_solution, formatted_solution

        # Save state after each iteration
        save_state()
