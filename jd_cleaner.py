"""
jd_cleaner.py
Strips common non-requirement boilerplate from job descriptions before scoring.
"""

import re

BOILERPLATE_PHRASES = [
    "equal opportunity employer", "background verification", "background check",
    "paid parental leave", "medical, dental, vision", "401(k)", "life insurance",
    "disability benefits", "wellness center", "counseling support",
    "we back you with benefits", "holistic well-being", "career development and training",
    "makes employment decisions without regard", "protected by law",
    "competitive base salar", "bonus incentive", "flexible working model",
]

METADATA_FIELD_LABELS = [
    "job info", "job identification", "posting date", "apply before",
    "job schedule", "job shift", "job category", "career area",
    "role type", "employment type", "work site", "travel", "profession",
    "discipline", "locations",
]


def _looks_like_metadata_footer_start(lines: list, start_index: int, window: int = 8) -> bool:
    chunk = " ".join(lines[start_index:start_index + window]).lower()
    hits = sum(1 for label in METADATA_FIELD_LABELS if label in chunk)
    return hits >= 3


def clean_jd_text(jd_text: str) -> dict:
    lines = jd_text.split("\n")

    footer_start = None
    for i in range(len(lines)):
        if _looks_like_metadata_footer_start(lines, i):
            footer_start = i
            break

    removed_footer = ""
    if footer_start is not None:
        removed_footer = "\n".join(lines[footer_start:]).strip()
        lines = lines[:footer_start]

    remaining_text = "\n".join(lines)
    paragraphs = re.split(r"\n\s*\n", remaining_text)
    kept_paragraphs = []
    removed_paragraphs = []

    for para in paragraphs:
        lower = para.lower()
        if any(phrase in lower for phrase in BOILERPLATE_PHRASES):
            removed_paragraphs.append(para.strip())
        else:
            kept_paragraphs.append(para)

    cleaned_text = "\n\n".join(p.strip() for p in kept_paragraphs if p.strip())

    return {
        "cleaned_text": cleaned_text,
        "removed_paragraphs": removed_paragraphs,
        "removed_footer": removed_footer,
        "original_word_count": len(jd_text.split()),
        "cleaned_word_count": len(cleaned_text.split()),
    }


if __name__ == "__main__":
    sample = """
Overview
We are looking for a great engineer.

Responsibilities
Build things. Fix bugs.

Competitive base salaries
Bonus incentives

American Express is an equal opportunity employer and makes employment decisions without regard to race.

Job Info
Job Identification
26011119
Posting Date
21/08/2026
Job Schedule
Full time
Locations
Gurugram, HR, IN
"""
    result = clean_jd_text(sample)
    print(result["cleaned_text"])
    print("Word count:", result["original_word_count"], "->", result["cleaned_word_count"])
