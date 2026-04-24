# Planner — Route Controller

Parse the user request and produce an execution plan.

## Input
- User instruction: {instruction}
- Analysis report: {analyst_report}

## Available phases
- analysis: Extract melody, harmony, voice roles, range check
- arrangement: Arrange for piano/strings/winds
- harmonist: Generate accompaniment from chord progression (optional, needs arrangement first)
- expression: Adjust velocity, timing, add pedal

## Output Format (JSON only)
{{
  "phases": ["analysis", "arrangement", "expression"],
  "params": {{
    "arrangement": {{"instrument": "piano", "style": "classical"}},
    "harmonist": {{"style": "classical", "pattern": "broken_chord"}},
    "expression": {{"melody_boost": 10, "accompaniment_reduce": 10, "timing": "rubato"}}
  }}
}}

Rules:
- "analysis" is always first
- "expression" is always last (if any arrangement was done)
- "harmonist" is optional — only include if the arrangement needs accompaniment
- Match the instrument/style to the user's request
- If user says "arrange for piano", use arrangement.instrument = "piano"
- If user says "classical", use style = "classical"
- If user says "romantic", use style = "romantic"
- If user says "pop", use style = "pop"
