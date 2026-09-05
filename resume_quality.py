"""
resume_quality.py
Resume-quality checks independent of any specific JD: weak phrasing, passive
voice, quantification, contact info, length, and real grammar checking via
LanguageTool (with false-positive filtering for tech terms AND the
candidate's own name).
"""

import re
import json
import requests

LANGUAGETOOL_API_URL = "https://api.languagetool.org/v2/check"
LANGUAGETOOL_TIMEOUT = 8

KNOWN_TERMS_PATH = "data/known_technical_terms.json"
TAXONOMY_PATH = "data/skills_taxonomy.json"
SYNONYMS_PATH = "data/skill_synonyms.json"

WEAK_STARTING_PHRASES = [
    "responsible for", "worked on", "helped with", "helped to", "assisted with",
    "assisted in", "involved in", "tasked with", "in charge of", "duties included",
    "was part of", "participated in", "contributed to",
]

PASSIVE_VOICE_PATTERN = re.compile(r"\b(was|were|is|are|been|being)\s+\w+ed\b", re.IGNORECASE)
PRONOUN_PATTERN = re.compile(r"\b(i|me|my|myself)\b", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"[\w\.\-]+@[\w\.\-]+\.\w+")
PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
QUANTIFICATION_PATTERN = re.compile(r"(\d|%|\$|\bx\d|\d+x\b)", re.IGNORECASE)


def load_spelling_allowlist(known_terms_path: str = KNOWN_TERMS_PATH,
                             taxonomy_path: str = TAXONOMY_PATH,
                             synonyms_path: str = SYNONYMS_PATH) -> set:
    """Combine the curated technical-term list with the skill taxonomy + synonyms."""
    terms = set()
    try:
        with open(known_terms_path, "r") as f:
            terms.update(t.lower() for t in json.load(f))
    except FileNotFoundError:
        pass
    try:
        with open(taxonomy_path, "r") as f:
            data = json.load(f)
            for skills in data.values():
                terms.update(s.lower() for s in skills)
    except FileNotFoundError:
        pass
    try:
        with open(synonyms_path, "r") as f:
            data = json.load(f)
            for phrases in data.values():
                terms.update(p.lower() for p in phrases)
    except FileNotFoundError:
        pass
    return terms


def extract_candidate_name_tokens(resume_text: str) -> set:
    """
    Best-effort guess at the candidate's own name from the first non-empty
    line of the resume (very common resume convention). Used to stop the
    grammar checker from flagging someone's own name as a spelling error.
    """
    lines = [l.strip() for l in resume_text.split("\n") if l.strip()]
    if not lines:
        return set()
    first_line = lines[0]
    # Only treat it as a name if it's short and has no digits/emails/symbols
    # (a real name line, not a stray header or contact-info line).
    if len(first_line.split()) <= 5 and not re.search(r"[\d@]", first_line):
        return {w.lower().strip(".,") for w in first_line.split()}
    return set()


def get_bullets(text: str) -> list:
    lines = re.split(r"[\n\r]+", text)
    return [line.strip() for line in lines if len(line.strip().split()) >= 5]


def check_weak_language(bullets: list) -> list:
    flagged = []
    for bullet in bullets:
        lower = bullet.lower()
        if any(phrase in lower for phrase in WEAK_STARTING_PHRASES):
            flagged.append(bullet)
    return flagged


def check_passive_voice(text: str) -> list:
    return PASSIVE_VOICE_PATTERN.findall(text)[:5]


def check_personal_pronouns(text: str) -> int:
    return len(PRONOUN_PATTERN.findall(text))


def check_quantification(bullets: list) -> dict:
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
    return {"has_email": bool(EMAIL_PATTERN.search(text)), "has_phone": bool(PHONE_PATTERN.search(text))}


def check_length(text: str) -> dict:
    word_count = len(text.split())
    if word_count < 150:
        verdict = "Likely too short — may be missing detail recruiters look for."
    elif word_count > 1000:
        verdict = "Likely too long — consider trimming to the most relevant, recent experience."
    else:
        verdict = "Reasonable length."
    return {"word_count": word_count, "verdict": verdict}


def check_grammar_languagetool(text: str, max_matches: int = 15, known_terms: set = None) -> dict:
    """
    Real grammar/spelling check via the free public LanguageTool API.
    Filters out: (1) known technical terms LanguageTool's dictionary doesn't
    recognize, (2) likely proper nouns (capitalized words mid-sentence — this
    catches the candidate's own name in most cases). Degrades gracefully on
    any network failure.
    """
    known_terms_lower = {t.lower() for t in (known_terms or set())}

    try:
        response = requests.post(
            LANGUAGETOOL_API_URL,
            data={"text": text, "language": "en-US"},
            timeout=LANGUAGETOOL_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return {"available": False, "issues": [], "filtered_technical_terms": 0}

    issues = []
    filtered_count = 0

    for match in data.get("matches", []):
        offset = match.get("offset", 0)
        length = match.get("length", 0)
        flagged_word = text[offset:offset + length].strip()
        category = match.get("rule", {}).get("category", {}).get("id", "")

        if flagged_word.lower().strip(".,;:") in known_terms_lower:
            filtered_count += 1
            continue

        is_capitalized_word = flagged_word[:1].isupper() and " " not in flagged_word
        preceding_char = text[:offset].rstrip()[-1:] if offset > 0 else ""
        mid_sentence = preceding_char not in ("", ".", "!", "?", "\n")
        if category == "TYPOS" and is_capitalized_word and mid_sentence:
            filtered_count += 1
            continue

        issues.append({
            "message": match.get("message", ""),
            "flagged_word": flagged_word,
            "category": match.get("rule", {}).get("category", {}).get("name", "Grammar"),
        })
        if len(issues) >= max_matches:
            break

    return {
        "available": True,
        "issues": issues,
        "total_found": len(issues),
        "filtered_technical_terms": filtered_count,
    }


def compute_quality_report(resume_text: str, check_grammar: bool = True) -> dict:
    bullets = get_bullets(resume_text)

    weak_bullets = check_weak_language(bullets)
    passive_matches = check_passive_voice(resume_text)
    pronoun_count = check_personal_pronouns(resume_text)
    quant_result = check_quantification(bullets)
    contact_result = check_contact_info(resume_text)
    length_result = check_length(resume_text)

    grammar_result = {"available": False, "issues": [], "filtered_technical_terms": 0}
    if check_grammar:
        allowlist = load_spelling_allowlist()
        allowlist |= extract_candidate_name_tokens(resume_text)
        grammar_result = check_grammar_languagetool(resume_text, known_terms=allowlist)

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
Built and deployed a REST API that reduced latency by 40%.
"""
    report = compute_quality_report(sample_resume, check_grammar=False)
    print(json.dumps(report, indent=2))
    print("Name tokens detected:", extract_candidate_name_tokens(sample_resume))
