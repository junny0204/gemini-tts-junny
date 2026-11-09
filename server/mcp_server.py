"""MCP server (stdio): Gemini 3.8 Flash TTS tools for Claude Code.

Installed and registered by install.py (https://github.com/junny0204/gemini-tts-junny):
    claude mcp add --transport stdio --scope user gemini-tts -- <venv python> <this file>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemini_tts as core  # noqa: E402


def _as_tool_error(exc: Exception) -> ToolError:
    # MCPServer only forwards ToolError text to the model; any other exception
    # becomes a bare "Error executing tool". Pass our explanations through.
    if isinstance(exc, core.TTSError):
        return ToolError(core.redact(str(exc)))
    if isinstance(exc, OSError):
        return ToolError(core.redact(f"檔案或系統錯誤：{exc}"))
    return ToolError(core.redact(f"{type(exc).__name__}: {exc}"))


async def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except Exception as exc:
        raise _as_tool_error(exc) from exc


def _play(path: str) -> None:
    try:
        core.play_audio(path)
    except Exception as exc:
        raise _as_tool_error(exc) from exc

_TIER_LINE = (
    "This install is set up as PAID tier: every request is billed from the Google project's prepaid credit;\n"
    "  HTTP 402 means the credit is used up (the user tops up at https://aistudio.google.com/billing)."
    if core.TIER == "paid" else
    "This install is set up as FREE tier: gemini-3.8-flash-tts allows only about 10 requests per day and 3 per\n"
    "  minute (shown at https://aistudio.google.com/rate-limit), reset at Pacific midnight\n"
    f"  (next reset {core._next_reset_local():%H:%M} local time)."
)
_ALT_LINE = " / the local IndexTTS2 (indextts2 skill)" if core.HAS_INDEXTTS2 else ""

INSTRUCTIONS = f"""\
Text-to-speech with Google Gemini 3.8 Flash TTS (WAV, 24 kHz, mono, 16-bit).
- `text` is read VERBATIM. Put sustained delivery (emotion, pace, tone) in `style`, never in `text`.
- Momentary sounds go inline in `text` as ENGLISH tags, even in Chinese text:
  <laugh> <chuckle> <sigh> <breath> <gasp> <cough> <whispers> <short pause> <long pause>.
- Always pass an absolute `output_path` (e.g. <current project>/tts_output/<name>.wav).
- Default model is gemini-3.8-flash-tts; use gemini-3.8-flash-lite-tts only when the user asks.
- {_TIER_LINE}
  Every call counts as one request however short the text, so: avoid needless regeneration, put several short
  lines in ONE call when they can be split afterwards, and check `used_today` / `quota_note` in each result.
- A call never hangs: daily-quota errors return at once with the reset time, and a request that gets no
  answer is stopped after about 150 s. Do not retry a daily-quota or 402 error the same day; ask the user
  whether to wait, add billing credit, or switch to gemini-3.8-flash-lite-tts{_ALT_LINE}.
- If no API key is found, call check_setup and follow `how_to_fix`. NEVER ask the user to paste the key into
  the chat, and never print or echo the key or the files that hold it.
- Errors come back in Traditional Chinese; relay them to the user as-is.
"""

mcp = MCPServer("gemini-tts", instructions=INSTRUCTIONS, version=core.__version__)

Voice = Annotated[
    str,
    Field(
        description="Prebuilt voice name (Kore, Puck, Zephyr, Charon, Aoede, Sulafat, ... 30 in total), "
        "an Extended Voice Library id from list_voices, or a custom voice_... id."
    ),
]
OutputPath = Annotated[
    str,
    Field(
        description="Absolute path of the .wav file to write, e.g. <project>/tts_output/intro.wav. "
        "Empty = ~/Music/GeminiTTS/tts_<timestamp>.wav. Existing files get a _1, _2 suffix unless overwrite=true."
    ),
]
Model = Annotated[str, Field(description="gemini-3.8-flash-tts (default) or gemini-3.8-flash-lite-tts.")]
Play = Annotated[bool, Field(description="Also play the audio on the user's speakers (only when they want to hear it).")]
Overwrite = Annotated[bool, Field(description="Overwrite output_path if it already exists.")]


class Turn(BaseModel):
    speaker: str = Field(description="Speaker name; must be a key of speaker_voices.")
    text: str = Field(description="Verbatim line for this turn (no 'Name:' prefix). Inline English tags allowed.")
    style: str = Field(default="", description="Optional short delivery direction for this turn only.")


@mcp.tool()
async def generate_speech(
    text: Annotated[str, Field(description="Verbatim transcript to speak. Inline English vocal tags allowed, e.g. <laugh>, <short pause>.")],
    voice: Voice = core.DEFAULT_VOICE,
    style: Annotated[str, Field(description="Short delivery direction for the whole text, e.g. 'warm and calm', 'cheerful', 'speaking slowly'. Empty = natural reading (usually best).")] = "",
    output_path: OutputPath = "",
    model: Model = core.DEFAULT_MODEL,
    play: Play = False,
    overwrite: Overwrite = False,
) -> dict[str, Any]:
    """Convert text to single-speaker speech and save it as a WAV file. Long scripts are split at paragraph/sentence boundaries and joined automatically."""
    result = await _call(
        core.synthesize, text, voice=voice, style=style, model=model,
        output_path=output_path, overwrite=overwrite,
    )
    if play:
        _play(result["path"])
        result["played"] = True
    return result


@mcp.tool()
async def generate_dialogue(
    turns: Annotated[list[Turn], Field(description="Ordered dialogue turns, one item per line spoken.")],
    speaker_voices: Annotated[dict[str, str], Field(description="Voice for each speaker, e.g. {'小明': 'Puck', '小美': 'Kore'}.")],
    output_path: OutputPath = "",
    model: Model = core.DEFAULT_MODEL,
    play: Play = False,
    overwrite: Overwrite = False,
) -> dict[str, Any]:
    """Render a multi-speaker dialogue into one WAV file. Exactly two speakers with prebuilt voices are generated natively (most natural, fewest requests); more speakers or custom voices are generated per speaker turn and joined."""
    result = await _call(
        core.synthesize_dialogue, turns, speaker_voices, model=model,
        output_path=output_path, overwrite=overwrite,
    )
    if play:
        _play(result["path"])
        result["played"] = True
    return result


@mcp.tool()
async def list_voices(
    search: Annotated[str, Field(description="Free-text search over voice name and description, e.g. 'Mandarin', 'Taiwan', 'narrator', 'warm'.")] = "",
    language_code: Annotated[list[str] | None, Field(description="BCP-47 language tags to filter by. Unsure of the exact code? Use `search` instead.")] = None,
    gender: Annotated[list[str] | None, Field(description="'female', 'male' and/or 'neutral'.")] = None,
    accent: Annotated[list[str] | None, Field(description="Accent descriptors, e.g. ['Taiwanese'].")] = None,
    voice_type: Annotated[list[str] | None, Field(description="'prebuilt', 'prompted' (voice design) and/or 'replicated'.")] = None,
    page_size: Annotated[int, Field(description="Max voices to return (1-200).")] = 30,
) -> dict[str, Any]:
    """Search the Gemini voice catalog: prebuilt voices, the Extended Voice Library and the user's custom voices."""
    return await _call(
        core.list_voices, search, language_code, gender, accent, voice_type, page_size
    )


@mcp.tool()
def play_audio(
    path: Annotated[str, Field(description="Absolute path of a WAV file to play.")] = "",
    stop: Annotated[bool, Field(description="Stop whatever is currently playing instead.")] = False,
) -> dict[str, Any]:
    """Play a WAV file on the user's speakers without waiting for it to finish, or stop playback."""
    if stop:
        core.stop_audio()
        return {"stopped": True}
    if not path:
        raise ToolError("請提供要播放的音檔路徑。")
    _play(path)
    return {"playing": str(Path(path))}


@mcp.tool()
async def check_setup(
    verify_key: Annotated[bool, Field(description="Also make one cheap metadata call to Google to confirm the key works (uses no text-to-speech quota).")] = False,
) -> dict[str, Any]:
    """Check versions, tier setting and whether the Gemini API key can be found. Never reveals the key. Without verify_key it makes no network call."""
    return await _call(core.check_setup, verify_key)


if __name__ == "__main__":
    mcp.run()
