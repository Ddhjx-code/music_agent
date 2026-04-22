"""
LLM-based tonal quantization of ABC notation.

Pipeline: raw ABC (from midi2abc) → LLM cleanup → quantized ABC → abc2midi → clean MIDI
"""

import json
import os
import re

from dotenv import load_dotenv

# Find .env relative to this module's parent project
_this_dir = os.path.dirname(__file__)
_env_path = os.path.join(_this_dir, '..', '.env')
load_dotenv(os.path.abspath(_env_path))


def build_quantize_prompt(abc_text: str, key: str = None, style: str = "clean_score") -> str:
    """Build the LLM prompt for ABC tonal quantization."""
    key_hint = f"\n- **Expected key**: {key}" if key else ""
    style_descriptions = {
        "clean_score": "Produce a clean, readable melody sheet with standard note values (1/8, 1/4, 1/2). No micro-rhythms.",
        "expressive": "Preserve some expressive timing variation while aligning to musical grid.",
        "minimal": "Minimal changes — only fix obvious transcription errors.",
    }
    style_desc = style_descriptions.get(style, style_descriptions["clean_score"])

    prompt = f"""You are a music engraver. Quantize the following ABC notation to produce a clean, readable musical score.

## Input ABC Notation
```
{abc_text}
```

## Instructions
{key_hint}
- **Style**: {style_desc}

Apply the following rules:
1. **Rhythmic quantization**: Align all note durations to standard musical subdivisions (1/8, 1/4, 1/2, whole). Remove micro-rhythms caused by transcription artifacts.
2. **Pitch consistency**: Ensure all notes fit within the declared key signature. Fix anomalous pitches that are likely transcription errors.
3. **Monophonic vocal line**: This is a single-voice melody. Remove any chord marks or polyphonic artifacts.
4. **Bar alignment**: Ensure each measure has the correct number of beats per the time signature (M: field).
5. **Readable formatting**: Use consistent line breaks and spacing. Group related musical phrases together.

## Output Format
Output ONLY the cleaned ABC notation, starting with the X: header line and ending with the last bar marker. Do NOT include any explanation, markdown code fences, or extra text.
"""
    return prompt


def quantize_abc(abc_text: str, key: str = None, style: str = "clean_score") -> str | None:
    """
    Use LLM to quantize ABC notation to a musically coherent score.

    Args:
        abc_text: Raw ABC notation string.
        key: Optional expected key (e.g. "E", "Am").
        style: Quantization style ("clean_score", "expressive", "minimal").

    Returns:
        Quantized ABC notation string, or None if LLM unavailable.
    """
    prompt = build_quantize_prompt(abc_text, key, style)

    try:
        import openai

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        model = os.environ.get("OPENAI_MODEL") or os.environ.get("DEFAULT_MODEL", "qwen-plus")

        if api_key:
            print(f"  LLM quantization: model={model}, base_url={base_url}")
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a music engraver. Output only valid ABC notation."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            result = response.choices[0].message.content
            # Strip markdown code fences if present
            result = re.sub(r'^```abc\s*', '', result, flags=re.MULTILINE)
            result = re.sub(r'^```\s*$', '', result, flags=re.MULTILINE)
            result = result.strip()
            return result
    except Exception as e:
        print(f"  LLM quantization unavailable: {e}")

    return None


def validate_abc(abc_text: str) -> bool:
    """Check if text looks like valid ABC notation (basic heuristic)."""
    return (
        "X:" in abc_text
        and "M:" in abc_text
        and "K:" in abc_text
        and "|" in abc_text
    )


def extract_key_from_abc(abc_text: str) -> str | None:
    """Extract key signature from ABC notation."""
    for line in abc_text.split("\n"):
        if line.startswith("K:"):
            return line[2:].strip().split("%")[0].strip()
    return None


def extract_title_from_abc(abc_text: str) -> str | None:
    """Extract title from ABC notation."""
    for line in abc_text.split("\n"):
        if line.startswith("T:"):
            return line[2:].strip()
    return None
