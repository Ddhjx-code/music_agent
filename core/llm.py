"""
LLM connection layer.

Reads configuration from .env and initializes a LangChain-compatible LLM.
Supports both OpenAI-compatible API and Claude API.
"""

import os
from pathlib import Path


def _load_env():
    """Load .env file if present."""
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip()
                    if key not in os.environ:
                        os.environ[key] = value


def get_llm():
    """
    Initialize and return an LLM instance based on .env configuration.

    Priority:
    1. If ANTHROPIC_API_KEY is set → use ChatAnthropic
    2. If OPENAI_API_KEY is set → use ChatOpenAI (compatible with any OpenAI-style API)

    Returns:
        A LangChain-compatible chat model instance.

    Raises:
        ValueError: If no API key is configured.
    """
    _load_env()

    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    openai_key = os.environ.get('OPENAI_API_KEY', '').strip()
    openai_base = os.environ.get('OPENAI_BASE_URL', '').strip()
    model = os.environ.get('DEFAULT_MODEL', '').strip() or None

    if anthropic_key:
        from langchain_anthropic import ChatAnthropic
        kwargs = {'model': model or 'claude-sonnet-4-6-20250514', 'api_key': anthropic_key}
        return ChatAnthropic(**kwargs)

    if openai_key:
        from langchain_openai import ChatOpenAI
        kwargs = {
            'model': model or 'gpt-4o',
            'api_key': openai_key,
            'temperature': 0,
        }
        if openai_base:
            kwargs['base_url'] = openai_base
        return ChatOpenAI(**kwargs)

    raise ValueError(
        "No LLM configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env"
    )
