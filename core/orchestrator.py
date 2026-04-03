"""
Orchestrator — the user-facing API for the Music Agent pipeline.

Wires together: MIDI I/O → music summary → LLM tool chain → output MIDI.
"""

import json
import os

from core.music_io import load_midi, save_midi
from core.json_schema import generate_summary
from agent.tool_registry import TOOLS, get_tool_by_name
from agent.prompt_templates import SYSTEM_PROMPT


def create_music_agent(llm):
    """
    Create a LangChain agent with all registered tools.

    Args:
        llm: A LangChain-compatible LLM instance.

    Returns:
        A LangChain agent.
    """
    try:
        from langchain.agents import create_openai_functions_agent, AgentExecutor
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        prompt = ChatPromptTemplate.from_messages([
            ('system', SYSTEM_PROMPT),
            ('human', '{input}'),
            MessagesPlaceholder(variable_name='agent_scratchpad'),
        ])

        agent = create_openai_functions_agent(llm, TOOLS, prompt)
        return AgentExecutor(agent=agent, tools=TOOLS, verbose=True)
    except ImportError:
        raise ImportError(
            "langchain is not installed. Run: pip install langchain langchain-openai"
        )


def run_pipeline(midi_path: str, instruction: str, llm,
                 output_path: str = None) -> str:
    """
    Run the full Music Agent pipeline.

    Args:
        midi_path: Path to the input MIDI file.
        instruction: Natural language instruction (e.g., "arrange as classical piano").
        llm: A LangChain-compatible LLM instance.
        output_path: Optional output MIDI path. Defaults to input path with _arranged suffix.

    Returns:
        Path to the output MIDI file.
    """
    # Step 1: Load MIDI
    piece = load_midi(midi_path)

    # Step 2: Generate summary for LLM
    summary = generate_summary(piece)

    # Step 3: Create agent
    agent = create_music_agent(llm)

    # Step 4: Run agent with instruction + summary
    prompt = (
        f"Here is a music summary:\n{json.dumps(summary, indent=2)}\n\n"
        f"User request: {instruction}"
    )
    result = agent.invoke({'input': prompt})

    # Step 5: The agent should have called arrange_for_piano
    # For now, we return the output from the agent
    # In a full implementation, the agent would save the MIDI and return the path
    if output_path is None:
        base, ext = os.path.splitext(midi_path)
        output_path = f"{base}_arranged{ext}"

    # The agent's output should include the arranged piece
    # For Phase 1, we save the original piece (the agent modifies it in-place
    # through tool calls in a more complete implementation)
    # Here we use the arrange_for_piano tool directly as a fallback
    from tools.arrangement.arrange_piano import ArrangePianoTool

    # Parse style from instruction
    style = 'classical'
    if 'romantic' in instruction.lower():
        style = 'romantic'
    elif 'pop' in instruction.lower():
        style = 'pop'

    arranged = ArrangePianoTool().run(piece, style=style)
    save_midi(arranged, output_path)

    return output_path
