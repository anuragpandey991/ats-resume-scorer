"""
resume_quality.py
Checks resume quality independent of any specific job description — the kind
of things real ATS/resume tools (Jobscan, Rezi, etc.) flag regardless of what
role you're applying for: weak phrasing, passive voice, missing contact info,
unquantified achievements, and real grammar issues via LanguageTool.
"""

import re
import json
import requests

LANGUAGETOOL_API_URL = "https://api.languagetool.org/v2/check"
LANGUAGETOOL_TIMEOUT = 8  # seconds — fail fast rather than hang the UI
KNOWN_TERMS_PATH = "data/known_technical_terms.json"

# Phrases that read as passive/low-impact compared to a strong action verb.
# Checked at the START of a bullet, since that's where resumes lose the most points.
WEAK_STARTING_PHRASES = [
    "responsible for", "worked on", "helped with", "helped to", "assisted with",
    "assisted in", "involved in", "tasked with", "in charge of", "duties included",
    "was part of", "participated in", "contributed to",
]

# Rough passive-voice heuristic: a form of "to be" followed by a past participle
# (word ending in -ed). Not perfect (misses irregular verbs like "was given"),
# but catches the most common resume pattern: "was responsible", "were assigned".
PASSIVE_VOICE_PATTERN = re.compile(r"\b(was|were|is|are|been|being)\s+\w+ed\b", re.IGNORECASE)

PRONOUN_PATTERN = re.compile(r"\b(i|me|my|myself)\b", re.IGNORECASE)

EMAIL_PATTERN = re.compile(r"[\w\.\-]+@[\w\.\-]+\.\w+")
PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

# A bullet "has quantification" if it contains a digit, %, $, or a multiplier like "3x".
QUANTIFICATION_PATTERN = re.compile(r"(\d|%|\$|\bx\d|\d+x\b)", re.IGNORECASE)


def get_bullets(text: str) -> list:
    """
    Split resume text into bullet-like lines for per-bullet checks.
    Filters out very short lines (section headers, single words) since those
    aren't achievement statements and would just add noise to the checks.
    """
    lines = re.split(r"[\n\r]+", text)
    return [line.strip() for line in lines if len(line.strip().split()) >= 5]


def check_weak_language(bullets: list) -> list:
    """
    Return bullets containing a weak/passive-sounding phrase. Checks anywhere
    in the bullet (not just the literal start) since resumes often lead with
    "I was responsible for..." — the pronoun would otherwise block a strict
    startswith check from ever matching.
    """
    flagged = []
    for bullet in bullets:
        lower = bullet.lower()
        if any(phrase in lower for phrase in WEAK_STARTING_PHRASES):
            flagged.append(bullet)
    return flagged


def check_passive_voice(text: str) -> list:
    """Return up to 5 example matches of passive-voice construction."""
    matches = PASSIVE_VOICE_PATTERN.findall(text)
    return matches[:5]


def check_personal_pronouns(text: str) -> int:
    """Count first-person pronoun usage — resumes conventionally avoid these."""
    return len(PRONOUN_PATTERN.findall(text))


def check_quantification(bullets: list) -> dict:
    """
    Percentage of achievement-style bullets that include a number/metric.
    Real recruiters and ATS ranking algorithms both favor quantified impact
    ("reduced runtime 75%") over vague claims ("improved runtime").
    Also returns the actual unquantified bullets (capped) so the UI can point
    to specific lines worth improving, not just a percentage.
    """
    if not bullets:
        return {"percent_quantified": 0.0, "quantified_count": 0, "total_bullets": 0, "unquantified_examples": []}

    quantified = [b for b in bullets if QUANTIFICATION_PATTERN.search(b)]
    unquantified = [b for b in bullets if not QUANTIFICATION_PATTERN.search(b)]
    percent = round(len(quantified) / len(bullets) * 100, 1)

    return {
        "percent_quantified": percent,
        "quantified_count": len(quantified),
        "total_bullets": len(bullets),
        "unquantified_examples": unquantified[:5],
    }


def check_contact_info(text: str) -> dict:
    """Check whether an email and phone number are detectable in the resume."""
    return {
        "has_email": bool(EMAIL_PATTERN.search(text)),
        "has_phone": bool(PHONE_PATTERN.search(text)),
    }


def check_length(text: str) -> dict:
    """
    Flag resumes that are likely too short (under-detailed) or too long
    (over one page equivalent for most early-to-mid career roles).
    These thresholds are heuristic guidance, not a hard rule.
    """
    word_count = len(text.split())
    if word_count < 150:
        verdict = "Likely too short — may be missing detail recruiters look for."
    elif word_count > 1000:
        verdict = "Likely too long — consider trimming to the most relevant, recent experience."
    else:
        verdict = "Reasonable length."
    return {"word_count": word_count, "verdict": verdict}


def load_spelling_allowlist(path: str = KNOWN_TERMS_PATH) -> set:
    """
    Build the set of technical terms/proper nouns that should NOT be flagged
    as spelling mistakes, even though a generic dictionary won't recognize
    them. Combines the curated known-terms list with our own skill taxonomy,
    since anything already in the taxonomy is by definition a real tech term.
    """
    allowlist = set()

    try:
        with open(path, "r") as f:
            allowlist.update(term.lower() for term in json.load(f))
    except FileNotFoundError:
        pass

    try:
        from keyword_matcher import load_taxonomy, load_synonyms
        for skill in load_taxonomy():
            allowlist.add(skill.lower())
        for phrases in load_synonyms().values():
            allowlist.update(p.lower() for p in phrases)
    except Exception:
        pass  # keyword_matcher unavailable for some reason — allowlist still works, just smaller

    return allowlist


def check_grammar_languagetool(text: str, max_matches: int = 8) -> dict:
    """
    Real grammar/spelling check via the free public LanguageTool API.
    Degrades gracefully (returns available=False) on any network failure,
    timeout, or rate limit — this should never crash the rest of the analysis.

    Spelling-category matches are cross-checked against a technical-term
    allowlist first — generic dictionaries don't know words like "PySpark"
    or "LangGraph", so without this filter, well-written technical resumes
    get flooded with false-positive "typos" that aren't actually wrong.
    """
    try:
        response = requests.post(
            LANGUAGETOOL_API_URL,
            data={"text": text, "language": "en-US"},
            timeout=LANGUAGETOOL_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return {"available": False, "issues": []}

    allowlist = load_spelling_allowlist()
    real_issues = []

    for match in data.get("matches", []):
        rule_info = match.get("rule", {})
        issue_type = rule_info.get("issueType", "")
        category = rule_info.get("category", {}).get("name", "Grammar")

        # Extract the exact flagged word using the API's offset/length, so we
        # can check it against our allowlist rather than guessing from the message.
        offset = match.get("offset", 0)
        length = match.get("length", 0)
        flagged_word = text[offset:offset + length].strip().lower()

        is_spelling_issue = issue_type == "misspelling" or category.lower() in ("possible typo", "typos")
        is_technical_typo = is_spelling_issue and flagged_word in allowlist

        if is_technical_typo:
            continue  # skip — this is a real technical term, not a typo

        real_issues.append({
            "message": match.get("message", ""),
            "context": match.get("context", {}).get("text", ""),
            "category": category,
            "flagged_word": flagged_word,
        })

    return {
        "available": True,
        "issues": real_issues[:max_matches],
        "total_found": len(real_issues),
        "filtered_technical_terms": len(data.get("matches", [])) - len(real_issues),
    }


def compute_quality_report(resume_text: str, check_grammar: bool = True) -> dict:
    """
    Run all quality checks and combine them into a single 0-100 quality score
    plus the raw findings from each check, for the UI/insight generator to use.
    """
    bullets = get_bullets(resume_text)

    weak_bullets = check_weak_language(bullets)
    passive_matches = check_passive_voice(resume_text)
    pronoun_count = check_personal_pronouns(resume_text)
    quant_result = check_quantification(bullets)
    contact_result = check_contact_info(resume_text)
    length_result = check_length(resume_text)
    grammar_result = check_grammar_languagetool(resume_text) if check_grammar else {"available": False, "issues": []}

    # Start at 100, deduct for each issue category found. Every deduction is
    # capped so no single category can tank the score on its own — this is a
    # readability/polish score, not a pass/fail gate.
    score = 100.0
    score -= min(15, len(weak_bullets) * 3)
    score -= min(10, len(passive_matches) * 2)
    score -= min(10, pronoun_count * 2)
    score -= min(15, max(0, (60 - quant_result["percent_quantified"]) / 4))
    score -= 0 if contact_result["has_email"] else 10
    score -= 0 if contact_result["has_phone"] else 5
    if grammar_result.get("available"):
        score -= min(20, grammar_result.get("total_found", 0) * 2)

    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "quality_score": score,
        "weak_language_bullets": weak_bullets,
        "passive_voice_matches": passive_matches,
        "pronoun_count": pronoun_count,
        "quantification": quant_result,
        "contact_info": contact_result,
        "length": length_result,
        "grammar": grammar_result,
    }


if __name__ == "__main__":
    sample_resume = """
    John Doe
    john.doe@email.com | 555-123-4567

    I was responsible for managing a team of 5 engineers.
    Helped with the migration of the database.
    Built and deployed a REST API that reduced latency by 40%.
    Assisted in the design of the new onboarding flow.
    """

    report = compute_quality_report(sample_resume, check_grammar=False)  # grammar off for offline test
    import json
    print(json.dumps(report, indent=2))
