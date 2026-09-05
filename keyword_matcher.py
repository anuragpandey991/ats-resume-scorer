"""
keyword_matcher.py
Matches skills from the static taxonomy against JD and resume text.
"""

import json
import re
from rapidfuzz import fuzz

TAXONOMY_PATH = "data/skills_taxonomy.json"
SYNONYMS_PATH = "data/skill_synonyms.json"
FUZZY_THRESHOLD = 85

# Abstract/soft skills eligible for the SBERT semantic fallback check.
# Concrete tools (AWS, Docker, React...) are deliberately excluded — semantically
# matching "cloud infrastructure" to "AWS" would be a real false-positive risk.
SEMANTIC_FALLBACK_SKILLS = {
    "Communication", "Data Analysis", "Problem Solving", "Leadership",
    "Collaboration", "Project Management", "Stakeholder Management",
    "Cross-functional Collaboration", "Critical Thinking", "Mentoring",
    "Time Management", "Team Management",
}


def load_taxonomy(path: str = TAXONOMY_PATH) -> list:
    with open(path, "r") as f:
        data = json.load(f)
    all_skills = []
    for category, skills in data.items():
        all_skills.extend(skills)
    return all_skills


def load_synonyms(path: str = SYNONYMS_PATH) -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _normalize(text: str) -> str:
    # Replace disallowed characters with a SPACE, not nothing — otherwise
    # slash/comma-separated lists like "C/C++" collapse into one fused token
    # ("cc++") and silently break word-boundary matching.
    text = re.sub(r"[^a-z0-9\s\+\#\.]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _phrase_found_in_text(phrase: str, normalized_text: str) -> bool:
    norm_phrase = _normalize(phrase)
    if not norm_phrase:
        return False

    pattern = r"(?<!\w)" + re.escape(norm_phrase) + r"(?!\w)"
    if re.search(pattern, normalized_text):
        return True

    if len(norm_phrase) > 3:
        words = normalized_text.split()
        window_size = len(norm_phrase.split())
        for i in range(len(words) - window_size + 1):
            window = " ".join(words[i:i + window_size])
            if fuzz.ratio(window, norm_phrase) >= FUZZY_THRESHOLD:
                return True
    return False


def find_skills_in_text(text: str, taxonomy: list, synonyms: dict = None) -> set:
    normalized_text = _normalize(text)
    synonyms = synonyms or {}
    found = set()

    for skill in taxonomy:
        if _phrase_found_in_text(skill, normalized_text):
            found.add(skill)
            continue
        for alt_phrase in synonyms.get(skill, []):
            if _phrase_found_in_text(alt_phrase, normalized_text):
                found.add(skill)
                break
    return found


def compute_keyword_match(jd_text: str, resume_text: str, taxonomy_path: str = TAXONOMY_PATH,
                           synonyms_path: str = SYNONYMS_PATH, use_semantic_fallback: bool = True) -> dict:
    taxonomy = load_taxonomy(taxonomy_path)
    synonyms = load_synonyms(synonyms_path)

    jd_skills = find_skills_in_text(jd_text, taxonomy, synonyms)
    resume_skills = find_skills_in_text(resume_text, taxonomy, synonyms)

    if not jd_skills:
        return {
            "match_percent": 0.0, "jd_skills": [], "matched_skills": [],
            "missing_skills": [], "semantic_matched_skills": [],
        }

    matched = jd_skills & resume_skills
    missing = jd_skills - resume_skills

    semantic_matched = set()
    if use_semantic_fallback and missing:
        candidates = [s for s in missing if s in SEMANTIC_FALLBACK_SKILLS]
        if candidates:
            try:
                from semantic_similarity import find_skills_semantically
                semantic_matched = find_skills_semantically(candidates, resume_text)
            except Exception:
                semantic_matched = set()

    matched = matched | semantic_matched
    missing = missing - semantic_matched

    match_percent = round(len(matched) / len(jd_skills) * 100, 1)

    return {
        "match_percent": match_percent,
        "jd_skills": sorted(jd_skills),
        "matched_skills": sorted(matched),
        "missing_skills": sorted(missing),
        "semantic_matched_skills": sorted(semantic_matched),
    }


if __name__ == "__main__":
    jd = "We need a Python developer with experience in Django, PostgreSQL, Docker, and AWS. Familiarity with React is a plus."
    resume = "I built REST APIs using Python and Flask, deployed on AWS with Docker containers."
    print(json.dumps(compute_keyword_match(jd, resume, use_semantic_fallback=False), indent=2))
