"""
Generates one Kling AI video clip per beat via fal.ai's hosted Kling API.

Why Kling specifically: it's the closest thing to the reference video's
quality among models actually reachable through a simple REST API — fluid
motion, strong prompt adherence, native audio support (which we disable,
since our own edge-tts narration is the audio track).

Default endpoint is Kling 1.6 Standard, not the Pro/2.6 tier — Standard is
priced low enough (~$0.05-0.10/generation at 5s) that fal.ai's one-time
free trial credit (~$10 on signup) covers a FULL multi-beat video, often
several, rather than being burned on one or two clips. Bump FAL_MODEL to
a Pro/2.6 endpoint in .env if you want higher quality and don't mind the
trial credit going further.

This is a trial-credit tool, not a recurring-free one: once the credit is
spent, generation calls start failing with a billing error. That's the
tradeoff for actually seeing full Kling-quality output, as requested.
"""
import os
import time
from pathlib import Path

import requests

FAL_MODEL = os.environ.get("FAL_VIDEO_MODEL", "fal-ai/kling-video/v1.6/standard/text-to-video")
CLIP_DURATION = os.environ.get("KLING_DURATION", "5")  # Kling supports "5" or "10" seconds

# Approximate fal.ai list price for Kling 1.6 Standard, audio off, as of
# this writing. Used only for the rough running-cost estimate main.py
# prints — NOT authoritative; always check your actual fal.ai dashboard
# balance for real spend.
KLING_COST_PER_SECOND = 0.056


def _build_prompt(beat) -> str:
    """Kling responds well to a full descriptive scene, not a bare keyword —
    turn the beat's short visual_keyword into a fuller cinematic prompt."""
    return (
        f"cinematic documentary shot, {beat.visual_keyword}, "
        "realistic lighting, high detail, slow deliberate camera movement, "
        "no text overlays, no watermarks"
    )


def _api_key() -> str:
    key = os.environ.get("FAL_KEY")
    if not key:
        raise EnvironmentError(
            "FAL_KEY not set. Copy .env.example to .env and fill it in. "
            "Get a free trial key at https://fal.ai/dashboard/keys"
        )
    return key


def generate_clip(beat, out_path: Path, poll_interval: float = 5.0, timeout: float = 300.0) -> Path | None:
    """Submits one Kling generation job, polls until done, downloads the
    result. Returns None on any failure so the assembler can fall back to
    a hold card for just that beat instead of crashing the whole run."""
    prompt = _build_prompt(beat)
    headers = {"Authorization": f"Key {_api_key()}"}
    submit_url = f"https://queue.fal.run/{FAL_MODEL}"

    payload = {
        "prompt": prompt,
        "duration": CLIP_DURATION,
        "aspect_ratio": "9:16",   # vertical, matches the final 1080x1920 output
        "generate_audio": False,  # our own edge-tts narration is the audio track
    }

    try:
        resp = requests.post(submit_url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        job = resp.json()
        status_url = job["status_url"]
        response_url = job["response_url"]

        elapsed = 0.0
        while elapsed < timeout:
            status_resp = requests.get(status_url, headers=headers, timeout=30)
            status_resp.raise_for_status()
            status = status_resp.json().get("status")
            if status == "COMPLETED":
                break
            if status == "FAILED":
                print("  [!] Kling generation failed (check fal.ai dashboard for the error/billing status)")
                return None
            time.sleep(poll_interval)
            elapsed += poll_interval
        else:
            print("  [!] Kling generation timed out")
            return None

        result_resp = requests.get(response_url, headers=headers, timeout=30)
        result_resp.raise_for_status()
        video_url = result_resp.json()["video"]["url"]

        video_resp = requests.get(video_url, stream=True, timeout=60)
        video_resp.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            for chunk in video_resp.iter_content(chunk_size=1 << 16):
                f.write(chunk)
        return out_path

    except Exception as e:
        print(f"  [!] Kling generation failed: {e}")
        return None


def fetch_clips_for_beats(beats: list, out_dir: Path) -> list[Path | None]:
    """beats: list of Beat objects with .visual_keyword. Returns a list of
    generated clip paths in beat order (None for any beat that failed —
    the assembler falls back to a hold frame for those)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path | None] = []

    for i, beat in enumerate(beats):
        out_path = out_dir / f"clip_{i:02d}.mp4"
        print(f"  generating beat {i} via Kling: '{beat.visual_keyword}'...")
        result = generate_clip(beat, out_path)
        if result is None:
            print(f"  [!] beat {i} generation failed, will use a hold card")
        paths.append(result)

    return paths


if __name__ == "__main__":
    from dataclasses import dataclass
    from dotenv import load_dotenv

    load_dotenv()

    @dataclass
    class _FakeBeat:
        visual_keyword: str

    beat = _FakeBeat("submarine hull rivets close up")
    out = generate_clip(beat, Path("./_kling_test/clip_00.mp4"))
    print("Generated:", out)
