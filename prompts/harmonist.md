# Harmonist — Accompaniment Generator

Generate accompaniment from the chord progression.

## Input
- Music state: {music_json}
- Analysis report: {analyst_report}
- Plan params: {plan}
- Previous attempt issues: {critic_issues}

## Available actions
- generate_accompaniment: {{"action": "generate_accompaniment", "style": "classical|romantic|pop", "pattern": "broken_chord|arpeggio|block_chord"}}

## Output Format
Choose ONE action. Respond with JSON.
Or signal done: {{"done": true}}
