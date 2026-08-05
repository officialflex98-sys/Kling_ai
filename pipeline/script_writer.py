"""
Turns a bare topic into a structured video script:
- a short on-screen title
- a list of narration "beats" (sentences), each tagged with a plain-English
  visual search keyword used later to generate a matching AI video clip

The beat/keyword split is the whole trick that makes auto-generated video
work for ANY topic: the model does the work of translating narration into
a concrete, filmable scene description, per beat, instead of one vague
prompt for the whole video.

Calls the Gemini API directly over REST with `requests` — no google-genai
or google-generativeai SDK. Both of those packages install under the
shared `google` namespace, which repeatedly conflicted with
google-api-python-client/google-auth-oauthlib (needed for the optional
YouTube uploader) and threw "ImportError: cannot import name 'genai' from
'google'". A plain HTTP POST has no such dependency and can't have that
conflict.

Model pinned to gemini-3.6-flash — the current stable GA Flash model as of
this writing (the earlier gemini-2.5-flash pin broke because Google closed
that model off to new API keys). Google retires/restricts Gemini model IDs
on a rolling schedule, so if this starts erroring again, check
https://ai.google.dev/gemini-api/docs/models for the current recommended
Flash model and update MODEL below.
"""
import json
import os
import re
from dataclasses import dataclass

import requests

MODEL = "gemini-3.6-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

SYSTEM_PROMPT = """You write scripts for short-form documentary-style videos \
(YouTube Shorts / TikTok, ~35-50 seconds spoken). Style: punchy, factual, \
one idea per sentence, hooks the viewer in the first line. No fluff, no \
"welcome back to my channel" filler.

You must return ONLY valid JSON, no markdown fences, no preamble, matching \
exactly this shape:

{
  "title": "short on-screen title, under 8 words",
  "beats": [
    {"narration": "one spoken sentence", "visual_keyword": "2-4 word stock footage search term"}
  ]
}

Rules:
- 6 to 9 beats total.
- Each "narration" is ONE sentence, spoken-language, no citations, no markdown.
- Each "visual_keyword" must describe something concretely filmable \
(e.g. "submarine hull rivets close up", "ocean waves aerial", \
"ancient stone blocks") — never an abstract phrase a camera can't capture.
- First beat must be a hook, not background/definition.
- Do not use the word "video" or refer to the channel/creator.
"""


@dataclass
class Beat:
    narration: str
    visual_keyword: str


@dataclass
class Script:
    topic: str
    title: str
    beats: list[Beat]

    @property
    def full_narration(self) -> str:
        return " ".join(b.narration for b in self.beats)


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences if the model added them despite instructions
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def write_script(topic: str) -> Script:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set. Copy .env.example to .env and fill it in. "
            "Get a free key at https://aistudio.google.com/apikey"
        )

    payload = {
        "contents": [{"parts": [{"text": f"Topic: {topic}"}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {"responseMimeType": "application/json"},
    }
    resp = requests.post(
        API_URL,
        params={"key": api_key},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()

    raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
    data = _extract_json(raw_text)

    beats = [
        Beat(narration=b["narration"], visual_keyword=b["visual_keyword"])
        for b in data["beats"]
    ]
    return Script(topic=topic, title=data["title"], beats=beats)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    topic = sys.argv[1] if len(sys.argv) > 1 else "how black holes evaporate"
    script = write_script(topic)
    print(f"TITLE: {script.title}\n")
    for i, b in enumerate(script.beats, 1):
        print(f"{i}. [{b.visual_keyword}] {b.narration}")
