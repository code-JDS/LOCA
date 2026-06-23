"""
Auto-split physics problems into sub-problems using LLM.

This script reads a JSONL file containing complete physics problems,
sends each problem (with its figures) to an LLM, and outputs a new JSONL
file where each problem is annotated with `pre_context` and `sub_problems`.

Usage:
    python scripts/auto_split_problems.py \
        --input problem_set/IPhO/2025/test_2.jsonl \
        --output problem_set/IPhO/2025/test_2_split.jsonl \
        --model gemini/gemini-2.5-pro
"""

import argparse
import asyncio
import json
import os
import re
import sys

# Add project root to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chat import direct_chat
from src.utils import load_jsonl

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = r"""You are an expert at analyzing physics competition problems. Your task is to split a complete physics problem into its individual sub-problems.

## Rules

1. **pre_context**: Extract the shared introduction / preamble that applies to ALL sub-problems. This typically includes the problem title, general setup description, and global assumptions. It should NOT include any text specific to a particular Part or sub-problem.

2. **sub_problems**: Each explicitly numbered/labeled question in the original problem becomes one sub-problem. For each sub-problem:
   - **id**: Use the EXACT label/numbering as it appears in the original problem text. For example, if the problem uses "A.1", "A.2", "B.1", keep those; if it uses "(a)", "(b)", "(c)", keep those; if it uses "1.", "2.", "3.", keep those; if it uses "Q1(i)", "Q1(ii)", keep those. Do NOT invent or reformat the labels.
   - **questions**: Include ALL text that is specific context for this sub-problem. This means:
     - If this is the first sub-problem of a new Part (e.g., A.1, B.1, C.1), include the Part header and any Part-specific introduction text.
     - Include any bridging text between the previous sub-problem and this one (e.g., new definitions, tables, figures references).
     - Include the question itself (the boxed/bordered question text).
   - **figure_indices**: A list of 0-based indices into the provided figure_paths array, indicating which figures are relevant to understanding and solving THIS sub-problem. A figure may be relevant to multiple sub-problems. Consider:
     - Figures explicitly mentioned in the sub-problem's question text.
     - Figures from the sub-problem's Part introduction that are needed for context.
     - Figures from earlier parts that are explicitly referenced in this sub-problem's context.

3. **Completeness**: The concatenation of `pre_context` + all sub-problem `questions` must cover ALL text in the original problem. Do not lose any text.

4. **Precision**: Copy text exactly as-is. Do not paraphrase, summarize, or modify any text. Preserve all LaTeX, HTML, and Markdown formatting.

## Output Format

Return ONLY a valid JSON object (no markdown code fences, no explanation) with this exact structure:

{
  "pre_context": "...",
  "sub_problems": [
    {
      "id": "A.1",
      "questions": "...",
      "figure_indices": [0, 1]
    },
    {
      "id": "A.2",
      "questions": "...",
      "figure_indices": [1]
    }
  ]
}"""

USER_PROMPT_TEMPLATE = """Here is a complete physics problem to split into sub-problems.

## Problem Text

{problem_text}

## Figure Paths (0-indexed)

{figure_paths_list}

Please analyze the problem and split it into sub-problems following the rules in your instructions. Return ONLY valid JSON."""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def extract_json_from_response(response: str) -> dict:
    """Extract JSON object from LLM response, handling markdown fences and LaTeX braces."""
    # Try direct parse first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try to extract from markdown code block
    patterns = [
        r'```json\s*\n(.*?)\n\s*```',
        r'```\s*\n(.*?)\n\s*```',
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Last resort: try each top-level '{' as a candidate JSON start.
    # This avoids being confused by LaTeX braces like \frac{a}{b}.
    # We look for '{"' or '{\n' patterns which are typical JSON object starts,
    # then use json.JSONDecoder to parse exactly one object from that position.
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{(?=\s*")', response):
        try:
            obj, _ = decoder.raw_decode(response, match.start())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Could not extract valid JSON from LLM response:\n{response[:500]}...")


async def split_single_problem(
    problem: dict,
    model: str,
    temperature: float = 0.0,
    max_retries: int = 3,
) -> dict:
    """
    Use LLM to split a single problem into sub-problems.

    Args:
        problem: Original problem dict from JSONL.
        model: LLM model identifier (e.g., "gemini/gemini-2.5-pro").
        temperature: Sampling temperature.
        max_retries: Number of retries on parse failure.

    Returns:
        New problem dict with `pre_context` and `sub_problems` fields added.
    """
    problem_id = problem["id"]
    problem_text = problem["questions"]
    figure_paths = problem.get("figure_paths", []) or []

    # Build figure paths description for the prompt
    if figure_paths:
        figure_paths_list = "\n".join(
            f"[{i}] {p}" for i, p in enumerate(figure_paths)
        )
    else:
        figure_paths_list = "(No figures)"

    user_content = USER_PROMPT_TEMPLATE.format(
        problem_text=problem_text,
        figure_paths_list=figure_paths_list,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    for attempt in range(1, max_retries + 1):
        print(f"  [Attempt {attempt}/{max_retries}] Calling LLM for problem {problem_id}...", flush=True)

        response = await direct_chat(
            model=model,
            messages=messages,
            image_paths=figure_paths if figure_paths else None,
            temperature=temperature,
        )

        try:
            result = extract_json_from_response(response)
        except ValueError as e:
            print(f"  ⚠️ Failed to parse JSON on attempt {attempt}: {e}", flush=True)
            if attempt == max_retries:
                print(f"  ❌ All retries exhausted for problem {problem_id}. Skipping split.", flush=True)
                return problem  # Return original without split
            continue

        # Validate structure
        if "pre_context" not in result or "sub_problems" not in result:
            print(f"  ⚠️ Missing required keys in response on attempt {attempt}", flush=True)
            if attempt == max_retries:
                return problem
            continue

        if not isinstance(result["sub_problems"], list) or len(result["sub_problems"]) == 0:
            print(f"  ⚠️ Empty or invalid sub_problems on attempt {attempt}", flush=True)
            if attempt == max_retries:
                return problem
            continue

        # Convert figure_indices to figure_paths
        for sp in result["sub_problems"]:
            indices = sp.pop("figure_indices", [])
            sp["figure_paths"] = [
                figure_paths[i] for i in indices
                if isinstance(i, int) and 0 <= i < len(figure_paths)
            ]

        # Build output
        output = dict(problem)  # shallow copy
        output["pre_context"] = result["pre_context"]
        output["sub_problems"] = result["sub_problems"]

        n_subs = len(result["sub_problems"])
        sub_ids = [sp["id"] for sp in result["sub_problems"]]
        print(f"  ✅ Problem {problem_id} split into {n_subs} sub-problems: {sub_ids}", flush=True)
        return output

    return problem  # Fallback


async def main():
    parser = argparse.ArgumentParser(
        description="Auto-split physics problems into sub-problems using LLM."
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to input JSONL file with complete problems."
    )
    parser.add_argument(
        "--output", "-o", required=True,
        help="Path to output JSONL file with split sub-problems."
    )
    parser.add_argument(
        "--model", "-m", default="gemini/gemini-2.5-pro",
        help="LLM model to use (default: gemini/gemini-2.5-pro)."
    )
    parser.add_argument(
        "--temperature", "-t", type=float, default=0.0,
        help="Sampling temperature (default: 0.0)."
    )
    parser.add_argument(
        "--max-retries", type=int, default=3,
        help="Max retries per problem on parse failure (default: 3)."
    )
    parser.add_argument(
        "--problem-ids", nargs="*", default=None,
        help="Only process specific problem IDs (default: all)."
    )

    args = parser.parse_args()

    # Load input
    print(f"Loading problems from {args.input}", flush=True)
    dataset = load_jsonl(args.input)
    print(f"  Found {len(dataset)} problem(s)", flush=True)

    # Filter by IDs if specified
    if args.problem_ids:
        dataset = [p for p in dataset if p["id"] in args.problem_ids]
        print(f"  Filtered to {len(dataset)} problem(s): {[p['id'] for p in dataset]}", flush=True)

    # Process each problem sequentially
    results = []
    for problem in dataset:
        pid = problem["id"]
        fig_count = len(problem.get("figure_paths", []) or [])
        print(f"\nProcessing problem {pid} ({fig_count} figure(s))...", flush=True)

        result = await split_single_problem(
            problem=problem,
            model=args.model,
            temperature=args.temperature,
            max_retries=args.max_retries,
        )
        results.append(result)

    # Save output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    print(f"\n{'=' * 60}")
    print(f"Results saved to {args.output}")
    print(f"  Total problems: {len(results)}")
    split_count = sum(1 for r in results if "sub_problems" in r)
    print(f"  Successfully split: {split_count}")
    for r in results:
        if "sub_problems" in r:
            subs = r["sub_problems"]
            print(f"    {r['id']}: {len(subs)} sub-problems -> {[s['id'] for s in subs]}")


if __name__ == "__main__":
    asyncio.run(main())
