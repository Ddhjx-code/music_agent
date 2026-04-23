"""Load prompt templates from the prompts/ directory."""

import os

_PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
_cache: dict[str, str] = {}


def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .md extension)."""
    if name not in _cache:
        path = os.path.join(_PROMPT_DIR, f"{name}.md")
        with open(path) as f:
            _cache[name] = f.read()
    return _cache[name]
