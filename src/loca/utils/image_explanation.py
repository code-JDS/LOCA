import os
from typing import Literal, Optional
import asyncio
import re
import copy
from src import ROOT_DIR, RESULT_ROOT_DIR, load_prompt
from src.chat import direct_chat
from src.arbiter import arbiter_for_voting
from src.secretary import structured_secretary

IMAGE_EXPLANATION_DIR = os.path.join(ROOT_DIR, "src/prompt/image_explanation")
PROMPT_IMAGE_EXPLANATION = load_prompt(os.path.join(IMAGE_EXPLANATION_DIR, "image_explanation.json"))
# PROMPT_IMAGE_EXPLANATION_PHYSICSMINIONS = load_prompt(os.path.join(IMAGE_EXPLANATION_DIR, "image_explanation_PhysicsMinions.json"))

MODEL_DEFAULT = "gemini/gemini-2.5-pro"

# Maximum number of concurrent image explanation tasks
MAX_CONCURRENT_STEPS = int(os.getenv("LOCA_MAX_CONCURRENT_STEPS", "3"))


async def image_explanation_solver(
    task_id: str,
    problem_statement: str,
    model: str = None,
    temperature: float = None,
    figure_paths: list[str] = None,
    cache_file: str = None,
) -> str:
    # Check for pre-written markdown explanations alongside each image
    if figure_paths:
        md_paths = [os.path.splitext(p)[0] + ".md" for p in figure_paths]
        if all(os.path.exists(mp) for mp in md_paths):
            parts = []
            for mp in md_paths:
                with open(mp, "r", encoding="utf-8") as f:
                    parts.append(f.read())
            local_explanation = "\n\n".join(parts)
            print(f"📖 Task {task_id}: Loaded pre-written image explanations from {len(md_paths)} markdown file(s)", flush=True)
            # Update cache so downstream breakpoint recovery stays consistent
            if cache_file:
                try:
                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        f.write(local_explanation)
                except Exception as e:
                    print(f"⚠️ Task {task_id}: Failed to write cache {cache_file}: {e}", flush=True)
            return local_explanation

    # Check cache first
    if cache_file and os.path.exists(cache_file):
        print(f"📖 Task {task_id}: Loading image explanation from cache: {cache_file}", flush=True)
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"⚠️ Task {task_id}: Failed to read cache {cache_file}: {e}. Regenerating...", flush=True)

    if not model:
        model = MODEL_DEFAULT

    messages = PROMPT_IMAGE_EXPLANATION
    # messages = PROMPT_IMAGE_EXPLANATION_PHYSICSMINIONS

    # Process each image concurrently with semaphore to limit concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_STEPS)
    
    async def explain_single_image(i: int, path: str) -> str:
        async with semaphore:
            # Deep copy messages to avoid modifying the original
            current_messages = copy.deepcopy(messages)
            
            # Use replace method to inject problem statement
            current_messages = current_messages.replace({
                "problem_statement": problem_statement
            })
            
            # Call direct_chat for this image
            return await direct_chat(
                model=model,
                messages=current_messages,
                image_paths=[path],
                temperature=temperature
            )
    
    # Create tasks for all images
    tasks = [explain_single_image(i, path) for i, path in enumerate(figure_paths)]
    
    # Execute all tasks concurrently (with semaphore limiting max concurrency)
    results = await asyncio.gather(*tasks)
    
    # Concatenate results sequentially
    final_explanation = "\n\n".join(results)

    # Write cache
    if cache_file:
        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(final_explanation)
        except Exception as e:
            print(f"⚠️ Task {task_id}: Failed to write cache {cache_file}: {e}", flush=True)

    return final_explanation
