"""
Turns a bare topic into a structured video script using the Gemini REST API.
"""

import json
import os
import re
from dataclasses import dataclass

import requests

MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You write scripts for short-form documentary-style videos
(YouTube Shorts / TikTok, ~35-50 seconds spoken). Style: punchy, factual,
one idea per sentence, hooks the viewer in the first line. No fluff.

Return ONLY valid JSON.

{
  "title": "short on-screen title, under 8 words",
  "beats": [
    {
      "narration": "one spoken sentence",
      "visual_keyword": "2-4 word stock footage search term"
    }
  ]
}

Rules:
- 6 to 9 beats.
- One sentence per beat.
- Concrete visual keywords.
- First beat must hook the viewer.
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
    def full_narration(self):
        return " ".join(b.narration for b in self.beats)


def _extract_json(text: str):
    text = text.strip()

    text = re.sub(r"^```json", "", text)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    text = text.strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("No JSON returned by Gemini.")

    return json.loads(match.group(0))


def write_script(topic: str) -> Script:
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not found.")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={api_key}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{SYSTEM_PROMPT}\n\nTopic: {topic}"
                    }
                ]
            }
        ]
    }

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )

    response.raise_for_status()

    result = response.json()

    raw_text = result["candidates"][0]["content"]["parts"][0]["text"]

    data = _extract_json(raw_text)

    beats = [
        Beat(
            narration=beat["narration"],
            visual_keyword=beat["visual_keyword"],
        )
        for beat in data["beats"]
    ]

    return Script(
        topic=topic,
        title=data["title"],
        beats=beats,
    )


if __name__ == "__main__":
    script = write_script("How submarines evolved into deep-sea predators")

    print(f"TITLE: {script.title}\n")

    for i, beat in enumerate(script.beats, 1):
        print(f"{i}. [{beat.visual_keyword}] {beat.narration}")
