import json
import os
import re
from dataclasses import dataclass

from google import genai

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
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(text)


def write_script(topic: str):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not found.")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=MODEL,
        contents=f"{SYSTEM_PROMPT}\n\nTopic: {topic}",
    )

    data = _extract_json(response.text)

    beats = [
        Beat(
            narration=b["narration"],
            visual_keyword=b["visual_keyword"],
        )
        for b in data["beats"]
    ]

    return Script(
        topic=topic,
        title=data["title"],
        beats=beats,
    )


if __name__ == "__main__":
    script = write_script("How submarines evolved into deep-sea predators")

    print(script.title)

    for beat in script.beats:
        print(beat.visual_keyword, "-", beat.narration)
