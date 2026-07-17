import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

def extract_and_parse_json(text: str) -> Optional[Any]:
    """
    Robustly extract and parse JSON from a model's raw text output.
    
    Handles:
    - Pure JSON strings.
    - JSON enclosed in markdown code blocks (e.g. ```json ... ```).
    - JSON objects or arrays surrounded by conversational text.
    - Both `{...}` objects and `[...]` arrays.
    
    Returns the parsed Python object (dict or list), or None if parsing fails.
    """
    if not text:
        return None

    text = text.strip()
    
    # 1. Fast path: try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Try extracting from markdown code blocks
    # Look for ```json ... ``` or just ``` ... ```
    block_pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
    for match in block_pattern.finditer(text):
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue

    # 3. Try finding the outermost JSON object or array by brace/bracket matching
    # We find the first '{' or '[' and the last '}' or ']'
    # Since we might have conversational text that contains braces, we try
    # to find the largest balanced block or just the outer boundaries.
    
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    
    # Determine which comes first, and if we have a valid ending
    start_idx = -1
    end_idx = -1
    
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_idx = first_brace
        end_idx = last_brace
    elif first_bracket != -1:
        start_idx = first_bracket
        end_idx = last_bracket

    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        candidate = text[start_idx : end_idx + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # If the greedy outer match fails (e.g. "Here is the json: {} and some code: {}"),
            # we could try more sophisticated balanced brace extraction, but often the 
            # greedy approach works for LLM outputs that emit exactly one main JSON object.
            pass

    # 4. Fallback: regex search for object-like structure (similar to old _extract_json_fragment)
    # This is less safe but catches some edge cases where brackets are messed up.
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to extract JSON from text snippet (first 100 chars): %r", text[:100])
    return None
