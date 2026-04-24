"""Shared utilities for roles."""

import json
import re


def extract_json(text: str, fallback: dict | None = None) -> dict:
    """Extract JSON from LLM response text.

    Tries markdown code block first, then raw JSON object.
    Returns fallback dict if no JSON found.
    """
    if fallback is None:
        fallback = {}
    match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        pass
    return fallback
