#!/usr/bin/env python3
"""
Runs the whole autopilot pipeline end to end:

    topic -> script -> voiceover -> stock clips -> captions -> final.mp4

Usage:
    python main.py                          # picks the next topic automatically
    python main.py --topic "black holes"     # forces a specific topic
    python main.py --upload                 # also auto-uploads to YouTube
"""
import argparse
import re
from pathlib import Path

from dotenv import load_dotenv

from pipeline.topic_picker import pick_topic
from pipeline.script_writer import write_script
from pipeline.voiceover import generate_beat_audio
from pipeline.video_generator import fetch_clips_for_beats, CLIP_DURATION, KLING_COST_PER_SECOND
from pipeline.captions import generate_captions
from pipeline.assembler import build_video

ROOT = Path(__file__).resolve().parent


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default=None, help="Force a specific topic instead of auto-picking one")
    parser.add_argument("--upload", action="store_true", help="Auto-upload the result to YouTube")
    parser.add_argument("--music", default=None, help="Path to a background music file (optional)")
    args = parser.parse_args()

    load_dotenv()

    topic = pick_topic(args.topic)
    slug = slugify(topic)
    run_dir = ROOT / "output" / slug
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== Topic: {topic} ===")

    print("[1/5] Writing script...")
    script = write_script(topic)
    print(f"  Title: {script.title}")
    for i, b in enumerate(script.beats):
        print(f"  {i}. [{b.visual_keyword}] {b.narration}")

    print("[2/5] Generating voiceover...")
    beat_audio_paths = generate_beat_audio(script.beats, run_dir / "audio")

    print("[3/5] Generating AI video clips...")
    clip_paths = fetch_clips_for_beats(script.beats, run_dir / "clips")

    successful_clips = sum(1 for p in clip_paths if p is not None)
    failed_clips = len(clip_paths) - successful_clips
    est_cost = successful_clips * int(CLIP_DURATION) * KLING_COST_PER_SECOND
    print(f"  {successful_clips}/{len(clip_paths)} clips generated "
          f"(~${est_cost:.2f} estimated spend this run)")
    if failed_clips:
        print(f"  {failed_clips} beat(s) will use a hold-card fallback instead")

    print("[4/5] Transcribing narration for captions...")
    # Concat the beat audio quickly just to transcribe it as one continuous
    # track so caption timestamps line up with the final assembled audio.
    import subprocess
    concat_list = run_dir / "_narration_concat.txt"
    concat_list.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in beat_audio_paths), encoding="utf-8"
    )
    full_narration = run_dir / "full_narration.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(full_narration)],
        check=True, capture_output=True,
    )
    captions_path = generate_captions(full_narration, run_dir / "captions.ass")

    print("[5/5] Assembling final video...")
    final_path = build_video(
        clip_paths=clip_paths,
        beat_audio_paths=beat_audio_paths,
        title=script.title,
        captions_ass=captions_path,
        out_path=run_dir / "final.mp4",
        work_dir=run_dir / "work",
        music_path=Path(args.music) if args.music else None,
    )
    print(f"\nDone: {final_path}")
    print(f"Estimated Kling spend this run: ~${est_cost:.2f}")

    spend_log = ROOT / "logs" / "kling_spend.log"
    spend_log.parent.mkdir(parents=True, exist_ok=True)
    with open(spend_log, "a", encoding="utf-8") as f:
        f.write(f"{topic} :: {successful_clips} clips :: ~${est_cost:.2f}\n")
    total_spend = 0.0
    for line in spend_log.read_text(encoding="utf-8").splitlines():
        try:
            total_spend += float(line.rsplit("~$", 1)[1])
        except (IndexError, ValueError):
            pass
    print(f"Estimated cumulative Kling spend (all runs so far): ~${total_spend:.2f} "
          f"of your ~$10 trial credit")

    if args.upload:
        from pipeline.uploader import upload_short
        upload_short(final_path, title=script.title, description=script.full_narration)


if __name__ == "__main__":
    main()
