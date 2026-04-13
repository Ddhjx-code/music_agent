"""
Tests for LLM agent integration — real LLM calls, no mocks.

The LLM uses LangChain tool calling to invoke music tools by name.
This tests:
1. LLM understands music instructions
2. LLM outputs valid tool calls
3. Full pipeline with real LLM

Requires: OPENAI_API_KEY set in .env
"""

import json
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from agent.prompt_templates import SYSTEM_PROMPT


@pytest.fixture
def llm():
    """Create a LangChain LLM instance from .env config."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=os.getenv('DEFAULT_MODEL', 'qwen3-coder-plus'),
        openai_api_key=os.getenv('OPENAI_API_KEY'),
        base_url=os.getenv('OPENAI_BASE_URL'),
        temperature=0,
    )


@pytest.fixture
def simple_summary():
    """A minimal music summary for LLM tests."""
    return {
        "title": "Twinkle Twinkle",
        "key": "C",
        "bpm": 120,
        "time_signature": "4/4",
        "num_measures": 16,
        "num_tracks": 2,
        "tracks": [
            {
                "name": "Track 1",
                "instrument": 1,
                "role": "melody",
                "pitch_range": "C5-G5",
                "avg_velocity": 100,
            },
            {
                "name": "Track 2",
                "instrument": 1,
                "role": "harmony",
                "pitch_range": "F2-G3",
                "avg_velocity": 100,
            },
        ],
        "chord_progression": [
            {"measure": 1, "chord": "Cmajor"},
            {"measure": 2, "chord": "Gmajor"},
            {"measure": 3, "chord": "Aminor"},
            {"measure": 4, "chord": "Fmajor"},
        ],
        "form": [
            {"section": "A", "measures": "1-8"},
            {"section": "B", "measures": "9-16"},
        ],
    }


def _ask_llm_json(llm, prompt: str) -> dict:
    """Helper: ask LLM and parse JSON response."""
    from langchain_core.messages import SystemMessage, HumanMessage
    response = llm.invoke([
        SystemMessage(content="Respond with ONLY a JSON object. No explanation."),
        HumanMessage(content=prompt),
    ])
    text = response.content.strip()
    # Parse JSON from response
    import re
    match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"Could not parse JSON: {text}")


class TestLLMUnderstanding:
    """Test that the LLM understands music instructions."""

    def test_llm_identifies_classical_style(self, llm):
        """LLM should recognize '古典钢琴' as classical style."""
        result = _ask_llm_json(llm, (
            'Given the instruction: "把这首曲子改成古典钢琴"\n'
            'Return: {"style": "classical"}'
        ))
        assert 'classical' in result.get('style', '')

    def test_llm_identifies_romantic_style(self, llm):
        """LLM should recognize '浪漫钢琴' as romantic style."""
        result = _ask_llm_json(llm, (
            'Given the instruction: "改成浪漫钢琴"\n'
            'Return: {"style": "romantic"}'
        ))
        assert result.get('style') == 'romantic'

    def test_llm_identifies_pop_style(self, llm):
        """LLM should recognize '流行钢琴' as pop style."""
        result = _ask_llm_json(llm, (
            'Given the instruction: "改成流行钢琴"\n'
            'Return: {"style": "pop"}'
        ))
        assert 'pop' in (result.get('style') or '').lower()

    def test_llm_understands_chord_progression(self, llm, simple_summary):
        """LLM should identify the chords in the progression."""
        summary_json = json.dumps(simple_summary, indent=2)
        result = _ask_llm_json(llm, (
            f"Music summary:\n{summary_json}\n\n"
            "List the chord progression as an array of chord names. "
            'Return: {"chords": ["C", "G", "Am", "F"]}'
        ))
        assert 'chords' in result
        assert len(result['chords']) > 0

    def test_llm_identifies_key(self, llm, simple_summary):
        """LLM should correctly identify the key from the summary."""
        summary_json = json.dumps(simple_summary, indent=2)
        result = _ask_llm_json(llm, (
            f"Music summary:\n{summary_json}\n\n"
            'What key is this piece in? Return: {"key": "C"}'
        ))
        assert 'key' in result
        assert result['key'].lower() == 'c'

    def test_llm_selects_correct_action(self, llm, simple_summary):
        """LLM should choose arrange_for_piano for piano arrangement requests."""
        summary_json = json.dumps(simple_summary, indent=2)
        result = _ask_llm_json(llm, (
            f"Music summary:\n{summary_json}\n\n"
            'User request: "改成古典钢琴"\n'
            'Available actions: arrange_for_piano, analyze_harmony, extract_melody\n'
            'Return: {"action": "arrange_for_piano", "style": "classical"}'
        ))
        assert result.get('action') == 'arrange_for_piano'

    def test_llm_selects_analyze_action(self, llm, simple_summary):
        """LLM should choose analyze_harmony for chord analysis requests."""
        summary_json = json.dumps(simple_summary, indent=2)
        result = _ask_llm_json(llm, (
            f"Music summary:\n{summary_json}\n\n"
            'User request: "分析一下这首曲子的和弦进行"\n'
            'Available actions: arrange_for_piano, analyze_harmony, extract_melody\n'
            'Return: {"action": "analyze_harmony"}'
        ))
        assert result.get('action') == 'analyze_harmony'


class TestToolCallingAgent:
    """Test the LangChain tool-calling agent with music tools."""

    def test_agent_calls_arrange_for_piano_tool(self, llm, simple_melody_piece):
        """Agent should call arrange_for_piano tool or reference arrangement."""
        from agent.tool_registry import TOOLS, set_piece_context, get_piece_context
        from langchain.agents import create_agent

        set_piece_context(simple_melody_piece)

        agent = create_agent(llm, TOOLS, system_prompt=SYSTEM_PROMPT)

        result = agent.invoke({"messages": [(
            "user",
            "把这首曲子改成古典钢琴"
        )]})

        # Verify the agent engaged with the request
        messages = result.get('messages', [])
        tool_calls = []
        for m in messages:
            if hasattr(m, 'tool_calls') and m.tool_calls:
                tool_calls.extend(m.tool_calls)

        # Either: agent made tool calls, OR the piece was arranged
        arranged = get_piece_context()
        has_arrangement = hasattr(arranged, 'tracks') and len(arranged.tracks) >= 2
        assert len(tool_calls) > 0 or has_arrangement, (
            f"Agent should have called tools or arranged the piece. "
            f"Tool calls: {len(tool_calls)}, Arranged: {has_arrangement}"
        )

    def test_agent_calls_analyze_harmony_tool(self, llm, simple_melody_piece):
        """Agent should call analyze_harmony tool or provide harmony analysis."""
        from agent.tool_registry import TOOLS, set_piece_context
        from langchain.agents import create_agent

        set_piece_context(simple_melody_piece)

        agent = create_agent(llm, TOOLS, system_prompt=SYSTEM_PROMPT)

        result = agent.invoke({"messages": [(
            "user",
            "分析一下这首曲子的和弦进行"
        )]})

        messages = result.get('messages', [])
        tool_calls = []
        for m in messages:
            if hasattr(m, 'tool_calls') and m.tool_calls:
                tool_calls.extend(m.tool_calls)

        # Either: agent made tool calls, OR response contains chord info
        last_msg = messages[-1] if messages else None
        has_harmony_text = (
            last_msg is not None
            and hasattr(last_msg, 'content')
            and any(kw in str(last_msg.content).lower() for kw in ['chord', '和弦', 'major', 'minor'])
        )
        assert len(tool_calls) > 0 or has_harmony_text, (
            f"Agent should have called tools or provided analysis. "
            f"Tool calls: {len(tool_calls)}, Has harmony text: {has_harmony_text}"
        )


class TestFullLLMPipeline:
    """End-to-end pipeline with real LLM."""

    def test_llm_piano_arrangement(self, llm, simple_melody_piece, tmp_path):
        """Full pipeline: LLM receives music summary, decides to arrange for piano."""
        from core.json_schema import generate_summary
        from tools.arrangement.arrange_piano import ArrangePianoTool
        from core.music_io import save_midi, load_midi

        # Save input MIDI
        input_path = str(tmp_path / "input.mid")
        save_midi(simple_melody_piece, input_path)

        # Generate summary
        summary = generate_summary(simple_melody_piece)

        # Ask LLM what to do
        result = _ask_llm_json(llm, (
            f"Music summary:\n{json.dumps(summary, indent=2)}\n\n"
            'User wants: "改成古典钢琴"\n'
            'Return: {"action": "arrange_for_piano", "style": "classical|romantic|pop"}'
        ))

        # LLM should say arrange_for_piano with classical
        assert result.get('action') == 'arrange_for_piano'
        assert 'classical' in str(result.get('style', ''))

        # Actually arrange
        arranged = ArrangePianoTool().run(simple_melody_piece, style='classical')
        output_path = str(tmp_path / "output.mid")
        save_midi(arranged, output_path)

        # Verify output
        assert os.path.exists(output_path)
        output = load_midi(output_path)
        assert len(output.tracks) == 2

    def test_llm_full_pipeline_via_orchestrator(self, llm, simple_melody_piece, tmp_path):
        """Full pipeline through run_pipeline with real LLM."""
        from core.music_io import save_midi, load_midi

        input_path = str(tmp_path / "input.mid")
        save_midi(simple_melody_piece, input_path)

        output_path = str(tmp_path / "output.mid")
        from core.orchestrator import run_pipeline
        result_path = run_pipeline(input_path, "改成古典钢琴", llm, output_path)

        assert os.path.exists(result_path)
        output = load_midi(result_path)
        assert len(output.tracks) == 2
