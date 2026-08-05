"""
Generates narration audio for free using edge-tts (Microsoft's TTS engine —
no API key, no usage cap, good-enough quality for daily faceless content).

Generates ONE audio file per beat (not one file for the whole script) so
the assembler can line up each stock clip's duration against its own beat's
audio length exactly, instead of guessing timing splits after the fact.
"""
import asyncio
import os
from pathlib import Path

import edge_tts

DEFAULT_VOICE = os.environ.get("TTS_VOICE", "en-US-GuyNeural")


async def _generate_one(text: str, out_path: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


def generate_beat_audio(beats: list, out_dir: Path, voice: str = DEFAULT_VOICE) -> list[Path]:
    """beats: list of Beat objects with .narration. Returns list of paths,
    one mp3 per beat, in order."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    async def _run_all():
        for i, beat in enumerate(beats):
            out_path = out_dir / f"beat_{i:02d}.mp3"
            await _generate_one(beat.narration, out_path, voice)
            paths.append(out_path)

    asyncio.run(_run_all())
    return paths


if __name__ == "__main__":
    from dataclasses import dataclass

    @dataclass
    class _FakeBeat:
        narration: str

    beats = [_FakeBeat("This is a test of the voiceover pipeline.")]
    paths = generate_beat_audio(beats, Path("./_vo_test"))
    print("Generated:", paths)
