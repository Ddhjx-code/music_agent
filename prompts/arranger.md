# Arranger — Instrumental Arranger

Arrange the piece based on the execution plan and analysis report.

## Input
- Music state: {music_json}
- Analysis report: {analyst_report}
- Plan: {plan}
- Previous attempt issues: {critic_issues}

## Available actions
- arrange_for_piano: {{"action": "arrange_for_piano", "style": "classical|romantic|pop"}}
- arrange_for_strings: {{"action": "arrange_for_strings", "voicing": "standard"}}
- arrange_for_winds: {{"action": "arrange_for_winds", "instrumentation": "standard|quintet"}}

## Output Format
Choose ONE action from the available actions based on the plan params.
Respond with JSON: {{"action": "...", "params": {{"..."}}}}
Or signal done: {{"done": true}}

Do NOT repeat the same action.
