#!/usr/bin/env python3

import argparse
import asyncio
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from src.chat import direct_chat


MODEL_DEFAULT = "gemini-2.5-flash"


def extract_final_answer(improved_solution: str) -> tuple[bool, str]:
    pattern_final = r'(?s)Final Answer[:\s]*(.*)$'
    matches_final = re.findall(pattern_final, improved_solution, re.IGNORECASE | re.MULTILINE)
    
    if not matches_final:
        # return None
        return False, "\n".join(improved_solution.strip().splitlines()[-5:])
    
    content_after_final = matches_final[-1]
    
    pattern_bracket = r'(?s)\[(.*?)\]'
    matches_bracket = re.findall(pattern_bracket, content_after_final)
    
    if matches_bracket:
        result = matches_bracket[-1].strip()
        # If the last 2 characters are '\\', remove them
        if result.endswith('\\'):
            result = result[:-2].strip()
        return True, result
    else:
        return False, content_after_final.strip()


async def compare_answers_with_llm(
    original_answer: str, 
    augmented_answer: str, 
    model: str,
    problem_id: str
) -> bool:
    """Use LLM to compare if two answers are equivalent."""
    
    prompt = f"""You are a physics expert tasked with comparing two mathematical / physical answers to determine if they are equivalent.
Please carefully analyze whether the "Final Answer" provided in the end of `Improved Answer` are equivalent to the answer provided in `Original Answer`.
You MUST NOT pay much attention to the intermediate steps, but focus on the final result.
For the final result, you should especially pay attention to the sign, the coefficients, and each symbol used.

Your response must end with exactly one of these symbols:
- ✅ if the answers are equivalent
- ❌ if the answers are not equivalent

Example response format 1:
The original answer shows... while the improved answer presents... [Some detailed comparison] After analysis, these represent the same result.
✅

Example response format 2:
The original answer shows... while the improved answer presents... [Some detailed comparison] After analysis, these represent different results.
❌

Now compare the given answers:
Original Answer: {original_answer}
Improved Answer: {augmented_answer}
"""

    try:
        response = await direct_chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        
        # Extract the last ✅ or ❌ from the response
        if '✅' in response:
            last_check = response.rfind('✅')
            last_cross = response.rfind('❌')
            if last_check > last_cross:
                return True
        
        if '❌' in response:
            last_check = response.rfind('✅')
            last_cross = response.rfind('❌')
            if last_cross > last_check:
                return False
        
        # If no clear symbol found, default to False
        print(f"Warning: Unclear LLM response for {problem_id}: {response[-100:]}")
        return False
        
    except Exception as e:
        print(f"Error comparing answers for {problem_id}: {e}")
        return False


async def compare_final_results(
    problem_id: str,
    a_0: str,
    a_aug: str,
    model: str = None,
    debug_a_0: bool = False,
    debug_a_aug: bool = False,
) -> bool:
    if model is None:
        model = MODEL_DEFAULT

    try:
        success_a_0, final_result_a_0 = extract_final_answer(a_0)
        success_a_aug, final_result_a_aug = extract_final_answer(a_aug)
        if (not success_a_0) and debug_a_0:
            print(f"⚠️ Warning: Could not extract final answer from original answer for {problem_id}. Using: {final_result_a_0}")
        if (not success_a_aug) and debug_a_aug:
            print(f"⚠️ Warning: Could not extract final answer from augmented answer for {problem_id}. Using: {final_result_a_aug}")
        is_equiv: bool = await compare_answers_with_llm(
            final_result_a_0, final_result_a_aug, model, problem_id
        )
    except Exception as e:
        print(f"Error processing answer comparison for {problem_id}: {e}")
    
    return is_equiv
