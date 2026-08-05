"""
Transcribes the final combined voiceover with faster-whisper (free, runs
locally, no API key, no per-call cost) to get accurate word-level timestamps,
then writes an .ass subtitle file styled as bold white text with the
currently-spoken word highlighted yellow — the "TikTok caption" look.

Using Whisper on our OWN generated audio (rather than trusting edge-tts's
word-boundary events) gives more reliable timestamps, especially once the
per-beat clips are concatenated into one continuous audio track.
"""
from pathlib import Path

from faster_whisper import WhisperModel

MODEL_SIZE = "base"  # good accuracy/speed tradeoff on CPU for short clips

FONT = "Arial Black"
FONT_SIZE = 20
PRIMARY_COLOR = "&H00FFFFFF"   # white, ASS is &HAABBGGRR
HIGHLIGHT_COLOR = "&H0000FFFF"  # yellow
OUTLINE_COLOR = "&H00000000"   # black outline for readability on any footage


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def _ass_header() -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{FONT},{FONT_SIZE * 4},{PRIMARY_COLOR},&H000000FF,{OUTLINE_COLOR},&H00000000,1,0,0,0,100,100,0,0,1,6,0,2,60,60,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def transcribe(audio_path: Path) -> list[dict]:
    """Returns a flat list of {word, start, end} dicts for the whole file."""
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), word_timestamps=True)

    words = []
    for segment in segments:
        for w in segment.words:
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return words


def build_ass_captions(words: list[dict], out_path: Path, group_size: int = 4) -> Path:
    """Groups words into short on-screen phrases (group_size words each) and,
    within each phrase's time window, emits one caption line per word so the
    active word is highlighted yellow while the rest of the phrase stays
    white — the karaoke-style effect from the reference video."""
    lines = [_ass_header()]

    for i in range(0, len(words), group_size):
        group = words[i:i + group_size]
        if not group:
            continue
        phrase_words = [w["word"] for w in group]

        for j, active in enumerate(group):
            styled = []
            for k, w in enumerate(phrase_words):
                color = HIGHLIGHT_COLOR if k == j else PRIMARY_COLOR
                styled.append(f"{{\\c{color}}}{w}")
            text = " ".join(styled)
            start = _fmt_ts(active["start"])
            end = _fmt_ts(active["end"])
            lines.append(f"Dialogue: 0,{start},{end},Caption,,0,0,0,,{text}\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    return out_path


def generate_captions(audio_path: Path, out_path: Path) -> Path:
    words = transcribe(audio_path)
    return build_ass_captions(words, out_path)


if __name__ == "__main__":
    import sys

    audio = Path(sys.argv[1])
    out = generate_captions(audio, audio.with_suffix(".ass"))
    print(f"Wrote {out}")
