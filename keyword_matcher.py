"""
keyword_matcher.py
Matches skills from the static taxonomy against JD and resume text.
Uses fuzzy matching (rapidfuzz) so minor variations (e.g. "Node JS" vs "Node.js")
still count as a match, while avoiding heavy NLP dependencies.
"""

import json
import re
from rapidfuzz import fuzz

TAXONOMY_PATH = "data/skills_taxonomy.json"
SYNONYMS_PATH = "data/skill_synonyms.json"
FUZZY_THRESHOLD = 85  # 0-100, higher = stricter match

# Skills eligible for the semantic fallback check (see find_skills_semantically
# in semantic_similarity.py). Restricted to abstract/soft skills where phrasing
# varies a lot and a false positive is low-stakes. Concrete tools/tech skills
# (AWS, Docker, React...) are deliberately EXCLUDED — semantically matching
# "cloud infrastructure" to "AWS" would be a real false positive risk, since
# the candidate might mean Azure or GCP, not AWS specifically.
SEMANTIC_FALLBACK_SKILLS = {
    "Communication", "Data Analysis", "Problem Solving", "Leadership",
    "Collaboration", "Project Management", "Stakeholder Management",
    "Cross-functional Collaboration", "Critical Thinking", "Mentoring",
    "Time Management", "Team Management",
}


def load_taxonomy(path: str = TAXONOMY_PATH) -> list:
    """Flatten the categorized taxonomy JSON into a single skill list."""
    with open(path, "r") as f:
        data = json.load(f)
    all_skills = []
    for category, skills in data.items():
        all_skills.extend(skills)
    return all_skills


def load_synonyms(path: str = SYNONYMS_PATH) -> dict:
    """
    Load the canonical-skill -> alternate-phrasings map.
    Returns {} if the file is missing, so this feature degrades gracefully
    rather than crashing the whole matcher.
    """
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _normalize(text: str) -> str:
    # Replace disallowed characters with a SPACE, not nothing — otherwise
    # slash/comma-separated lists like "C/C++" or "Excel,PowerBI" collapse
    # into one fused token (e.g. "cc++") and silently break word-boundary matching.
    text = re.sub(r"[^a-z0-9\s\+\#\.]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _phrase_found_in_text(phrase: str, normalized_text: str) -> bool:
    """
    Check whether a single phrase (already normalized, or normalized here) is
    present in normalized_text — exact word-boundary match first, fuzzy
    sliding-window fallback for longer phrases. Shared by both direct skill
    names and their synonym phrases so the matching rules stay identical.
    """
    norm_phrase = _normalize(phrase)
    if not norm_phrase:
        return False

    # 1. Exact whole-word/phrase match
    pattern = r"(?<!\w)" + re.escape(norm_phrase) + r"(?!\w)"
    if re.search(pattern, normalized_text):
        return True

    # 2. Fuzzy sliding-window match (skip very short phrases — see keyword_matcher notes)
    if len(norm_phrase) > 3:
        words = normalized_text.split()
        window_size = len(norm_phrase.split())
        for i in range(len(words) - window_size + 1):
            window = " ".join(words[i:i + window_size])
            if fuzz.ratio(window, norm_phrase) >= FUZZY_THRESHOLD:
                return True

    return False


def find_skills_in_text(text: str, taxonomy: list, synonyms: dict = None) -> set:
    """
    Return the set of taxonomy skills found in the given text.
    A skill counts as found if either its own name matches, or any of its
    known synonym phrases (from `synonyms`) matches — this catches common
    paraphrasing like "data analytics" for "Data Analysis" or "led a team"
    for "Leadership", which pure exact/fuzzy name-matching would miss.
    """
    normalized_text = _normalize(text)
    synonyms = synonyms or {}
    found = set()

    for skill in taxonomy:
        if _phrase_found_in_text(skill, normalized_text):
            found.add(skill)
            continue

        # Check synonym phrases for this skill, if any are defined
        for alt_phrase in synonyms.get(skill, []):
            if _phrase_found_in_text(alt_phrase, normalized_text):
                found.add(skill)
                break

    return found


def compute_keyword_match(jd_text: str, resume_text: str, taxonomy_path: str = TAXONOMY_PATH,
                           synonyms_path: str = SYNONYMS_PATH, use_semantic_fallback: bool = True) -> dict:
    """
    Compare JD and resume against the skill taxonomy (plus synonym phrases).
    Returns match percentage and the specific missing/matched skills.

    use_semantic_fallback: if True, abstract/soft skills that are still
    "missing" after exact+synonym matching get one more check via SBERT
    semantic similarity against resume sentences (see semantic_similarity.py).
    This requires the SBERT model to be loaded, which needs internet access
    on first run — set False to skip this step entirely (e.g. offline testing).
    """
    taxonomy = load_taxonomy(taxonomy_path)
    synonyms = load_synonyms(synonyms_path)

    jd_skills = find_skills_in_text(jd_text, taxonomy, synonyms)
    resume_skills = find_skills_in_text(resume_text, taxonomy, synonyms)

    if not jd_skills:
        # JD didn't mention any taxonomy skills at all — can't score keyword match meaningfully
        return {
            "match_percent": 0.0,
            "jd_skills": [],
            "matched_skills": [],
            "missing_skills": [],
            "semantic_matched_skills": [],
        }

    matched = jd_skills & resume_skills
    missing = jd_skills - resume_skills

    semantic_matched = set()
    if use_semantic_fallback and missing:
        # Only re-check missing skills that are BOTH in our curated abstract-skill
        # allowlist AND actually required by this JD — no point checking skills
        # the JD never asked for.
        candidates = [s for s in missing if s in SEMANTIC_FALLBACK_SKILLS]
        if candidates:
            try:
                from semantic_similarity import find_skills_semantically
                semantic_matched = find_skills_semantically(candidates, resume_text)
            except Exception:
                # If the SBERT model can't load (no internet, first-run download
                # failed, etc.), silently skip the fallback rather than crashing
                # the whole keyword match — exact/synonym results are still valid.
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

    result = compute_keyword_match(jd, resume)
    print(json.dumps(result, indent=2))
