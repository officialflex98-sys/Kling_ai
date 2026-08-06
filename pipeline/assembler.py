"""
Stitches everything into the final vertical MP4 using ffmpeg (via subprocess
— no heavy Python video library needed, ffmpeg alone is free and does all
of this natively).

Steps:
1. For each beat: scale+crop its stock clip to fill 1080x1920, trim/loop it
   to exactly match that beat's narration audio duration (so visuals and
   voice never drift out of sync). Beats with no clip get a solid-color
   "hold" card instead of failing the whole run.
2. Concatenate all beat clips into one silent visual track.
3. Concatenate all beat audio files into one narration track.
4. Mux visuals + narration, optionally ducking in background music underneath.
5. Burn in the .ass captions and a title card, producing final.mp4.
"""
import subprocess
from pathlib import Path


def _wrap_title(title: str, max_chars: int = 18) -> str:
    """Breaks a long title into centered lines so drawtext never runs off
    the sides of a 1080px-wide frame — a single unwrapped line was the
    cause of titles getting cut off at both edges."""
    words = title.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n\n{result.stderr[-3000:]}")


def _probe_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _make_beat_visual(clip_path: Path | None, duration: float, out_path: Path) -> None:
    """Scale+crop to fill 1080x1920 and force exact duration. If clip_path
    is None (no footage matched), render a plain hold card instead so one
    missing clip never kills the whole run."""
    if clip_path is None:
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:s=1080x1920:d={duration}",
            "-t", str(duration), str(out_path),
        ]
        _run(cmd)
        return

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,fps=30"
    )
    cmd = [
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip_path),
        "-vf", vf, "-an", "-t", str(duration), str(out_path),
    ]
    _run(cmd)


def _concat(file_paths: list[Path], out_path: Path) -> None:
    list_file = out_path.parent / f"_{out_path.stem}_concat.txt"
    list_file.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in file_paths), encoding="utf-8"
    )
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(out_path),
    ]
    _run(cmd)


def build_video(
    clip_paths: list[Path | None],
    beat_audio_paths: list[Path],
    title: str,
    captions_ass: Path,
    out_path: Path,
    work_dir: Path,
    music_path: Path | None = None,
) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)

    beat_visuals = []
    for i, (clip, audio) in enumerate(zip(clip_paths, beat_audio_paths)):
        duration = _probe_duration(audio)
        out = work_dir / f"beat_visual_{i:02d}.mp4"
        _make_beat_visual(clip, duration, out)
        beat_visuals.append(out)

    visuals_concat = work_dir / "visuals.mp4"
    _concat(beat_visuals, visuals_concat)

    narration_concat = work_dir / "narration.mp3"
    _concat(list(beat_audio_paths), narration_concat)

    muxed = work_dir / "muxed.mp4"
    if music_path and music_path.exists():
        cmd = [
            "ffmpeg", "-y",
            "-i", str(visuals_concat),
            "-i", str(narration_concat),
            "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex",
            "[2:a]volume=0.10[music];[1:a][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-shortest", "-c:v", "copy", str(muxed),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(visuals_concat),
            "-i", str(narration_concat),
            "-map", "0:v", "-map", "1:a",
            "-shortest", "-c:v", "copy", "-c:a", "aac", str(muxed),
        ]
    _run(cmd)

    # 5. Burn captions + title card
    title_wrapped = _wrap_title(title)
    title_escaped = title_wrapped.replace("'", "\u2019").replace(":", "\\:")
    title_filter = (
        f"drawtext=text='{title_escaped}':fontfile=/usr/share/fonts/truetype/"
        "dejavu/DejaVuSans-Bold.ttf:fontsize=46:fontcolor=yellow:"
        "borderw=3:bordercolor=black:x=(w-text_w)/2:y=140:line_spacing=10:"
        "enable='between(t,0,3.5)'"
    )
    vf = f"{title_filter},ass={captions_ass}"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(muxed),
        "-vf", vf, "-c:a", "copy", str(out_path),
    ]
    _run(cmd)

    return out_path
