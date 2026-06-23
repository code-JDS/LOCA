import os
import json
import asyncio
import time
from src.utils import (load_jsonl, Problem, extract_problem, create_aux_dir)
from src.single_llm import single_llm_solver
from src.loca.utils.image_explanation import image_explanation_solver
from src.loca.solver import loca_solver
from src.vanilla_review.solver import vanilla_review_solver


SCHEMES_NEEDING_AUX_DIR = [
    'single-llm',
    'loca',
    'vanilla_review',
]


async def _run_loca_single(
    task_id: str,
    question_statement: str,
    figure_paths: list[str] | None,
    output_aux_path: str | None,
    single_llm_cache_path: str | None,
    generator_model: str,
    refine_model: str | None,
    reviewer_model: str,
    vision_model: str | None,
    generator_temperature: float,
    n_image_explanation: int,
    max_error_times: int,
    target_times: int,
    ablation: bool,
    keep_aug: bool,
    keep_specific_verification: bool,
    n_interpretation: int,
    stepwise_review: bool,
) -> tuple[bool, str, str | None]:
    """
    Run a single LOCA cycle (initial solution + iterative review) for one problem or sub-problem.
    
    Returns:
        (success, improved_solution, formatted_solution)
    """
    # Apply image explanation
    if n_image_explanation > 0 and figure_paths:
        cache_file_path = os.path.join(output_aux_path, "image_explanation.md") if output_aux_path else None
        image_explanation = await image_explanation_solver(
            task_id=task_id,
            problem_statement=question_statement,
            model=vision_model or generator_model,
            temperature=generator_temperature,
            figure_paths=figure_paths,
            cache_file=cache_file_path,
        )
        figure_paths = []  # Clear figure paths; image_explanation is the only image source
    else:
        image_explanation = ""

    # Get or generate initial solution
    existing_solution = None
    if single_llm_cache_path and os.path.exists(single_llm_cache_path):
        with open(single_llm_cache_path, "r") as f:
            existing_solution = f.read()
        print(f"⚠️ Warning: cache exists for {task_id}, using cached solution", flush=True)

    if existing_solution is not None:
        initial_solution = existing_solution
    else:
        print(f"🔄 Task {task_id}: Initializing with single-llm scheme", flush=True)
        single_llm_options = {"structured_output": True}
        initial_solution, _ = await single_llm_solver(
            task_id,
            question_statement,
            image_explanation,
            model=generator_model,
            temperature=generator_temperature,
            options=single_llm_options,
            figure_paths=figure_paths,
        )
        print(f"📝 Task {task_id}: Initial solution generated", flush=True)
        if single_llm_cache_path:
            os.makedirs(os.path.dirname(single_llm_cache_path), exist_ok=True)
            with open(single_llm_cache_path, "w") as f:
                f.write(initial_solution)

    # Call LOCA solver
    success, improved_solution, formatted_solution = await loca_solver(
        task_id=task_id,
        question_statement=question_statement,
        solution=initial_solution,
        image_explanation=image_explanation,
        output_aux_path=output_aux_path,
        augmentation_model=refine_model or generator_model,
        review_model=reviewer_model or generator_model,
        max_error_times=max_error_times,
        target_times=target_times,
        temperature=generator_temperature,
        ablation=ablation,
        keep_aug=keep_aug,
        keep_specific_verification=keep_specific_verification,
        n_interpretation=n_interpretation,
        stepwise_review=stepwise_review,
        figure_paths=figure_paths,
    )

    return success, improved_solution, formatted_solution


async def _solve_loca_sub_problems(
    problem: Problem,
    aux_dir: str | None,
    generator_model: str,
    refine_model: str | None,
    reviewer_model: str,
    vision_model: str | None,
    generator_temperature: float,
    n_image_explanation: int,
    max_error_times: int,
    target_times: int,
    ablation: bool,
    keep_aug: bool,
    keep_specific_verification: bool,
    n_interpretation: int,
    stepwise_review: bool,
) -> dict | None:
    """
    Solve a problem that has been split into sub-problems, sequentially using LOCA.
    
    Each sub-problem is solved independently through the full LOCA pipeline.
    Previous sub-problems' questions and final answers (without reasoning) are
    prepended as context for subsequent sub-problems.
    
    Returns:
        Aggregated result dict, or None if all sub-problems failed.
    """
    problem_id = problem["id"].replace("/", "_")
    pre_context = problem.get("pre_context", "")
    sub_problems = problem["sub_problems"]

    # Parent aux directory
    parent_aux_path = os.path.join(aux_dir, problem_id) if aux_dir else None
    if parent_aux_path and not os.path.exists(parent_aux_path):
        os.makedirs(parent_aux_path, exist_ok=True)

    # Load sub-problem progress state for breakpoint recovery
    sub_state_path = os.path.join(parent_aux_path, "sub_problem_progress.json") if parent_aux_path else None
    sub_results: dict = {}
    if sub_state_path and os.path.exists(sub_state_path):
        try:
            with open(sub_state_path, 'r', encoding='utf-8') as f:
                sub_results = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            sub_results = {}

    all_success = True

    for i, sub in enumerate(sub_problems):
        sub_id = sub["id"]
        composite_id = f"{problem_id}_sub_{sub_id}"

        # --- Breakpoint recovery: skip already completed sub-problems ---
        if sub_id in sub_results and sub_results[sub_id].get("completed"):
            print(f"✅ Sub-problem {sub_id} of {problem_id} already completed, skipping", flush=True)
            if not sub_results[sub_id].get("success"):
                all_success = False
            continue

        # --- Build context for this sub-problem ---
        context_parts = []
        if pre_context:
            context_parts.append(pre_context)

        context_parts.append(f"\n\n---\n\n**Sub-problems you have already solved:**\n{problem['questions']}")

        for j in range(i):
            prev_sub = sub_problems[j]
            prev_id = prev_sub["id"]
            prev_result = sub_results.get(prev_id, {})
            prev_answer = prev_result.get("formatted_solution", "[Not available]")
            # Include previous sub-problem's question (text only, no images) and final answer
            context_parts.append(
                f"\n\n---\n\n**Solved sub-problem [{prev_id}]**\n{prev_sub['questions']}"
                f"\n\n**Answer for [{prev_id}]:**\n{prev_answer}"
            )

        context_parts.append(f"\n\n---\n\n**[Current sub-problem to solve: {sub_id}]**\n{sub['questions']}")
        question_statement = "\n".join(context_parts)

        # Sub-problem's own figure paths
        sub_figure_paths = sub.get("figure_paths", [])

        # Sub-problem aux directories
        sub_aux_path = os.path.join(parent_aux_path, f"sub_{sub_id}") if parent_aux_path else None
        if sub_aux_path and not os.path.exists(sub_aux_path):
            os.makedirs(sub_aux_path, exist_ok=True)
        sub_single_llm_cache = os.path.join(parent_aux_path, f"sub_{sub_id}.cache.txt") if parent_aux_path else None

        print(f"🔄 Solving sub-problem {sub_id} ({i + 1}/{len(sub_problems)}) of {problem_id}", flush=True)

        success, improved_solution, formatted_solution = await _run_loca_single(
            task_id=composite_id,
            question_statement=question_statement,
            figure_paths=sub_figure_paths,
            output_aux_path=sub_aux_path,
            single_llm_cache_path=sub_single_llm_cache,
            generator_model=generator_model,
            refine_model=refine_model,
            reviewer_model=reviewer_model,
            vision_model=vision_model,
            generator_temperature=generator_temperature,
            n_image_explanation=n_image_explanation,
            max_error_times=max_error_times,
            target_times=target_times,
            ablation=ablation,
            keep_aug=keep_aug,
            keep_specific_verification=keep_specific_verification,
            n_interpretation=n_interpretation,
            stepwise_review=stepwise_review,
        )

        # Persist sub-problem result
        sub_results[sub_id] = {
            "completed": True,
            "success": success,
            "improved_solution": improved_solution,
            "formatted_solution": formatted_solution or "",
        }
        if sub_state_path:
            with open(sub_state_path, 'w', encoding='utf-8') as f:
                json.dump(sub_results, f, ensure_ascii=False, indent=2)

        if success:
            print(f"✅ Sub-problem {sub_id} of {problem_id} passed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}", flush=True)
        else:
            print(f"❌ Sub-problem {sub_id} of {problem_id} failed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}", flush=True)
            all_success = False

    # --- Aggregate results from all sub-problems ---
    all_solutions = []
    all_formatted = []
    for sub in sub_problems:
        result = sub_results.get(sub["id"], {})
        all_solutions.append(f"## [{sub['id']}]\n{result.get('improved_solution', '')}")
        all_formatted.append(f"## [{sub['id']}]\n{result.get('formatted_solution', '')}")

    combined_solution = "\n\n---\n\n".join(all_solutions)
    combined_formatted = "\n\n---\n\n".join(all_formatted)

    if all_success:
        print(f"✅ All sub-problems of {problem_id} passed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}", flush=True)
        return problem | {
            "improved_solutions": combined_solution,
            "formatted_solutions": "### Final Answer\n" + combined_formatted,
        }
    else:
        print(f"❌ Some sub-problems of {problem_id} failed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}", flush=True)
        return problem | {
            "improved_solutions": combined_solution,
            "formatted_solutions": "### Final Answer\n" + combined_formatted,
        }


async def solve_problem(problem: Problem, scheme: str,
                        tools: list[str] = None,
                        aux_dir: str = None,
                        extra_params: dict = None) -> dict:
    problem_id = problem["id"].replace("/", "_")
    problem_statement = problem["questions"]
    figure_paths = problem.get("figure_paths")
    generator_model = extra_params.get('generator_model') if extra_params else None
    planner_model = extra_params.get('planner_model') if extra_params else None
    reviewer_model = extra_params.get('reviewer_model') if extra_params else None
    vision_model = extra_params.get('vision_model') if extra_params else None
    
    # Parse temperature parameters with default value 0.0
    generator_temperature = float(extra_params.get('generator_temperature', 0.0)) if extra_params else 0.0
    planner_temperature = float(extra_params.get('planner_temperature', 0.0)) if extra_params else 0.0
    reviewer_temperature = float(extra_params.get('reviewer_temperature', 0.0)) if extra_params else 0.0
    
    # Parse reviewer options from extra_params
    refine_model = None
    voting_n = 1  # Default voting_n to 1
    
    # Parse single_llm options from extra_params
    zero_shot_cot = False  # Default to False
    cot = False  # Default to False
    structured_output = False  # Default to False
    
    # Parse LOCA options from extra_params
    max_error_times = 5  # Default value
    target_times = 3     # Default value
    ablation = False     # Default value
    keep_aug = False  # Default value
    keep_specific_verification = False  # Default value
    force_terminate = False  # Default value
    n_interpretation = 0  # Default value
    stepwise_review = False  # Default value
    n_image_explanation = 0  # Default value
    sub_problem_mode = False  # Default value: solve sub-problems sequentially
    
    if extra_params:
        
        # Handle string to boolean conversion for reviewer options
        if 'refine_model' in extra_params:
            refine_model = extra_params['refine_model']
        if 'voting_n' in extra_params:
            voting_n = int(extra_params['voting_n'])
            if scheme not in ["single-llm"]:
                raise ValueError("voting_n is only applicable for and single-llm schemes")
        
        # Handle single_llm options
        if 'zero_shot_cot' in extra_params:
            zero_shot_cot = str(extra_params['zero_shot_cot']).lower() in ('true', '1', 'yes')
        if 'cot' in extra_params:
            cot = str(extra_params['cot']).lower() in ('true', '1', 'yes')
        if 'structured_output' in extra_params:
            structured_output = str(extra_params['structured_output']).lower() in ('true', '1', 'yes')
            if scheme != "single-llm":
                raise ValueError("structured_output is only applicable for single-llm scheme")
        
        # Handle LOCA options
        if 'max_error_times' in extra_params:
            max_error_times = int(extra_params['max_error_times'])
            if scheme not in ["loca", "vanilla_review"]:
                raise ValueError("max_error_times is only applicable for loca and vanilla_review schemes")
        if 'target_times' in extra_params:
            target_times = int(extra_params['target_times'])
            if scheme not in ["loca", "vanilla_review"]:
                raise ValueError("target_times is only applicable for loca and vanilla_review schemes")
        if 'ablation' in extra_params:
            ablation = str(extra_params['ablation']).lower() in ('true', '1', 'yes')
            if scheme != "loca":
                raise ValueError("ablation is only applicable for loca scheme")
        if 'keep_aug' in extra_params:
            keep_aug = str(extra_params['keep_aug']).lower() in ('true', '1', 'yes')
            if scheme != "loca":
                raise ValueError("keep_aug is only applicable for loca scheme")
        if 'keep_specific_verification' in extra_params:
            keep_specific_verification = str(extra_params['keep_specific_verification']).lower() in ('true', '1', 'yes')
            if scheme != "loca":
                raise ValueError("keep_specific_verification is only applicable for loca scheme")
        if 'force_terminate' in extra_params:
            force_terminate = str(extra_params['force_terminate']).lower() in ('true', '1', 'yes')
            if scheme not in ["loca", "single-llm"]:
                raise ValueError("force_terminate is only applicable for loca and single-llm scheme")
            if scheme == "loca":
                raise ValueError("force_terminate is not recommended for loca scheme as it may lead to incomplete evaluation. Please use it with caution.")
        if 'n_interpretation' in extra_params:
            n_interpretation = int(extra_params['n_interpretation'])
            if scheme != "loca":
                raise ValueError("n_interpretation is only applicable for loca scheme")
        if 'stepwise_review' in extra_params:
            stepwise_review = str(extra_params['stepwise_review']).lower() in ('true', '1', 'yes')
            if scheme != "loca":
                raise ValueError("stepwise_review is only applicable for loca scheme")
        if 'n_image_explanation' in extra_params:
            n_image_explanation = int(extra_params['n_image_explanation'])
            if scheme != "loca":
                raise ValueError("n_image_explanation is only applicable for loca scheme")
            if n_image_explanation > 0:
                print("⚠️ Self-refine for image explanation is not implemented yet.", flush=True)
                print("⚠️ Image explanation is only compatible within the LOCA scheme.", flush=True)
        if 'sub_problem' in extra_params:
            sub_problem_mode = str(extra_params['sub_problem']).lower() in ('true', '1', 'yes')
            if scheme != "loca":
                raise ValueError("sub_problem is only applicable for loca scheme")
        
    if scheme == "single-llm":
        output_aux_path = os.path.join(aux_dir, problem_id + ".cache.txt") if aux_dir else None
        if output_aux_path is not None and os.path.exists(output_aux_path):
            with open(output_aux_path, "r") as f:
                solution = f.read()
                formatted_solutions = "No formatted solutions loaded from cache."
            print(f"⚠️ Warning: cache exists for problem {problem['id']}, skip it", flush=True)
        elif force_terminate and (output_aux_path is None or not os.path.exists(output_aux_path)):
            print(f"❌ Task {problem_id}: force_terminate is True but cache does not exist, returning Failed", flush=True)
            return problem | {"improved_solutions": "", "formatted_solutions": "\\[\n\\boxed{ Failed}\n\\]"}
        else:
            print(f"Solving problem {problem_id} with single-llm scheme", flush=True)
            single_llm_options = {
                "zero_shot_cot": zero_shot_cot,
                "cot": cot,
                "voting_n": voting_n,
                "structured_output": structured_output,
            }
            
            solution, formatted_solutions = await single_llm_solver(problem_id, problem_statement,
                                               model=generator_model,
                                               temperature=generator_temperature,
                                               options=single_llm_options,
                                               figure_paths=figure_paths,)
            if output_aux_path:
                # Check if the directory exists, if not, create it
                if not os.path.exists(os.path.dirname(output_aux_path)):
                    os.makedirs(os.path.dirname(output_aux_path), exist_ok=True)
                # Write the solution to the cache file
                with open(output_aux_path, "w") as f:
                    f.write(solution)
        return problem | {"improved_solutions": solution, "formatted_solutions": formatted_solutions}
    elif scheme == "loca":
        # Sub-problem mode: solve sub-problems sequentially
        if sub_problem_mode and problem.get("sub_problems"):
            print(f"📋 Task {problem_id}: sub_problem mode enabled, found {len(problem['sub_problems'])} sub-problem(s)", flush=True)
            return await _solve_loca_sub_problems(
                problem=problem,
                aux_dir=aux_dir,
                generator_model=generator_model,
                refine_model=refine_model,
                reviewer_model=reviewer_model or generator_model,
                vision_model=vision_model,
                generator_temperature=generator_temperature,
                n_image_explanation=n_image_explanation,
                max_error_times=max_error_times,
                target_times=target_times,
                ablation=ablation,
                keep_aug=keep_aug,
                keep_specific_verification=keep_specific_verification,
                n_interpretation=n_interpretation,
                stepwise_review=stepwise_review,
            )

        # LOCA solver - iterative review and refinement with retry logic
        output_aux_path = os.path.join(aux_dir, problem_id) if aux_dir else None
        if output_aux_path and not os.path.exists(output_aux_path):
            os.makedirs(output_aux_path, exist_ok=True)
        
        # Apply image explanation
        # NOTE: Self-refine for image explanation is not implemented yet
        if n_image_explanation > 0 and figure_paths:
            cache_file_path = os.path.join(output_aux_path, "image_explanation.md") if output_aux_path else None
            image_explanation = await image_explanation_solver(
                        task_id=problem_id,
                        problem_statement=problem_statement,
                        model=vision_model or generator_model,
                        temperature=generator_temperature,
                        figure_paths=figure_paths,
                        cache_file=cache_file_path,
                    )
            figure_paths = []  # Clear figure paths. Thus, `image_explanation` serves as the only source of image information
        else:
            image_explanation = ""
            # Preserve original figure paths if no image explanation is applied
        
        # Determine initial solution
        output_aux_single_llm = os.path.join(aux_dir, problem_id + ".cache.txt") if aux_dir else None
        
        # Check if single-llm cache exists
        existing_solution = None
        if output_aux_single_llm is not None and os.path.exists(output_aux_single_llm):
            with open(output_aux_single_llm, "r") as f:
                existing_solution = f.read()
            print(f"⚠️ Warning: cache exists for problem {problem['id']}, using cached solution", flush=True)
        
        if existing_solution is not None:
            initial_solution = existing_solution
        else:
            # Generate new initial solution using single-llm
            print(f"🔄 Task {problem_id}: Initializing problem {problem_id} with single-llm scheme", flush=True)
            single_llm_options = {"structured_output": True}
            initial_solution, formatted_initial_solutions = await single_llm_solver(
                problem_id, 
                problem_statement,
                image_explanation,
                model=generator_model,
                temperature=generator_temperature,
                options=single_llm_options,
                figure_paths=figure_paths,
            )
            print(f"📝 Task {problem_id}: Initial solution generated", flush=True)
            
            # Save the origin solution to aux single-llm cache
            if output_aux_single_llm:
                # Check if the directory exists, if not, create it
                if not os.path.exists(os.path.dirname(output_aux_single_llm)):
                    os.makedirs(os.path.dirname(output_aux_single_llm), exist_ok=True)
                # Write the solution to the cache file
                with open(output_aux_single_llm, "w") as f:
                    f.write(initial_solution)
        
        # Call LOCA solver
        success, improved_solution, formatted_solution = await loca_solver(
            task_id=problem_id,
            question_statement=problem_statement,
            solution=initial_solution,
            image_explanation=image_explanation,
            output_aux_path=output_aux_path,
            augmentation_model=refine_model or generator_model,
            review_model=reviewer_model or generator_model,
            max_error_times=max_error_times,
            target_times=target_times,
            temperature=generator_temperature,
            ablation=ablation,
            keep_aug=keep_aug,
            keep_specific_verification=keep_specific_verification,
            n_interpretation=n_interpretation,
            stepwise_review=stepwise_review,
            figure_paths=figure_paths,
        )

        if success:
            print(f"✅ Task {problem_id} passed review successfully at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}", flush=True)
            return problem | {"improved_solutions": improved_solution, "formatted_solutions": "### Final Answer\n" + formatted_solution}
        else:
            print(f"❌ Task {problem_id} failed review at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}", flush=True)
            return None

    elif scheme == "vanilla_review":
        # Vanilla Review solver - simple review with consistency checking
        output_aux_path = os.path.join(aux_dir, problem_id) if aux_dir else None
        if output_aux_path and not os.path.exists(output_aux_path):
            os.makedirs(output_aux_path, exist_ok=True)
        
        # Get initial solution from problem data (assuming it's in the solutions field)
        initial_solution = problem.get("solutions", "")
        if not initial_solution:
            raise ValueError(f"Vanilla Review scheme requires an initial solution in the 'solutions' field for problem {problem['id']}")
        
        success, result = await vanilla_review_solver(
            task_id=problem_id,
            question_statement=problem_statement,
            solution=initial_solution,
            output_aux_path=output_aux_path,
            review_model=reviewer_model or generator_model,
            max_error_times=max_error_times,
            target_times=target_times,
            temperature=reviewer_temperature
        )
        
        if success:
            return problem | {"vanilla_review_result": success}
        else:
            return problem | {"vanilla_review_result": success}
    else:
        raise ValueError(f"Unsupported scheme: {scheme}")

async def main(input_path: str, output_path: str, scheme: str = 'single-llm',
               tools: list[str] = [],
               extra_args: list[str] = None) -> None:
    print("\nArgs parsed successfully, starting processing...", flush=True)
    # Validate input file exists
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Create output directory if needed
    output_dir = os.path.dirname(output_path)
    if output_dir:  # Only create if path contains directory
        os.makedirs(output_dir, exist_ok=True)

    # Create auxiliary directory if needed
    aux_dir = os.path.join(os.path.dirname(output_path), ".aux") if scheme in SCHEMES_NEEDING_AUX_DIR else None
    if aux_dir:
        # Ensure the auxiliary directory exists for multi-round scheme
        if not os.path.exists(aux_dir):
            print(f"Creating auxiliary directory: {aux_dir}")
            os.makedirs(aux_dir, exist_ok=True)

    extra_params = {}
    if extra_args:
        i = 0
        while i < len(extra_args):
            if extra_args[i].startswith('--'):
                key = extra_args[i][2:]
                if i + 1 < len(extra_args) and not extra_args[i + 1].startswith('--'):
                    extra_params[key] = extra_args[i + 1]
                    i += 2
                    continue
                else:
                    extra_params[key] = True
            i += 1

    print(f"Processing input: {input_path}", flush=True)
    print(f"Using scheme: {scheme}", flush=True)
    print(f"Tools selected :{tools}", flush=True)
    print(f"Extra arguments:", flush=True)
    for key, value in extra_params.items():
        print(f"  {key}: {value}", flush=True)
    print(f"Output will be directed to {output_dir}, where results will be deposited in {output_path}\n", flush=True)
    dataset = load_jsonl(input_path)
    problem_set = [extract_problem(pwa) for pwa in dataset]
    task_list = [solve_problem(problem, scheme, tools, aux_dir, extra_params) for problem in problem_set]
    results = await asyncio.gather(*task_list)
    
    # Save results to specified output path
    with open(output_path, "w") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"\nResults saved to {output_path}\n")
