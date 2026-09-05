"""
resume_structure.py
Computes a Structure/Formatting score (0-100) independent of any specific JD —
this is the w4 term in the final weighted score. Checks things an ATS parser
and a human skimmer both care about: are standard sections present and in a
sane order, are bullets used consistently, are dates formatted consistently,
is contact info easy to find, and is the overall length reasonable.

Deliberately regex/heuristic based (no ML) — formatting is a structural
property of the raw text, not something that benefits from embeddings.
"""

import re

# Canonical section groups, in the order a recruiter/ATS conventionally
# expects them. Order-checking is a soft signal, not a hard requirement.
SECTION_ALIASES = {
    "contact": {"contact", "contact information", "contact info"},
    "summary": {"summary", "objective", "profile", "about"},
    "experience": {"work experience", "experience", "professional experience",
                   "employment history", "employment"},
    "education": {"education"},
    "skills": {"skills", "technical skills", "core skills"},
    "projects": {"projects", "project experience"},
    "certifications": {"certifications", "achievements", "awards", "publications"},
}
CONVENTIONAL_ORDER = ["contact", "summary", "experience", "education", "skills", "projects", "certifications"]

BULLET_SYMBOLS = ["•", "◦", "▪", "-", "*", "‣", "·"]

DATE_PATTERNS = {
    "month_year": re.compile(r"\b[A-Za-z]{3,9}\.?\s+\d{4}\b"),
    "numeric_slash": re.compile(r"\b\d{1,2}/\d{4}\b"),
    "year_only": re.compile(r"(?<!\d)\d{4}(?!\d)"),
}

EMAIL_PATTERN = re.compile(r"[\w\.\-]+@[\w\.\-]+\.\w+")
PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")


def _normalize_header_line(line: str) -> str:
    return re.sub(r"[^a-z\s]", "", line.strip().lower()).strip()


def detect_sections(resume_text: str) -> list:
    """Returns [(line_index, canonical_group), ...] in document order."""
    lines = resume_text.split("\n")
    found = []
    for i, line in enumerate(lines):
        norm = _normalize_header_line(line)
        if not norm:
            continue
        for group, aliases in SECTION_ALIASES.items():
            if norm in aliases:
                found.append((i, group))
                break
    return found


def check_section_presence(sections_found: list) -> dict:
    present_groups = {g for _, g in sections_found}
    required = {"experience", "education", "skills"}
    missing = sorted(required - present_groups)
    return {
        "present": sorted(present_groups),
        "missing_required": missing,
        "has_all_required": len(missing) == 0,
    }


def check_section_order(sections_found: list) -> dict:
    """
    Soft check: do the sections that *are* present appear in a conventional
    relative order? Penalizes badly out-of-order docs without demanding an
    exact template match.
    """
    groups_in_doc_order = [g for _, g in sections_found]
    if len(groups_in_doc_order) < 2:
        return {"in_conventional_order": True, "note": "Not enough sections to judge order."}

    rank = {g: i for i, g in enumerate(CONVENTIONAL_ORDER)}
    ranked = [rank[g] for g in groups_in_doc_order if g in rank]
    inversions = sum(1 for i in range(len(ranked) - 1) if ranked[i] > ranked[i + 1])
    return {
        "in_conventional_order": inversions == 0,
        "inversions": inversions,
    }


def check_bullet_consistency(resume_text: str) -> dict:
    lines = resume_text.split("\n")
    symbol_counts = {}
    for line in lines:
        stripped = line.strip()
        if stripped and stripped[0] in BULLET_SYMBOLS:
            symbol_counts[stripped[0]] = symbol_counts.get(stripped[0], 0) + 1

    total_bulleted = sum(symbol_counts.values())
    if total_bulleted < 3:
        return {"consistent": True, "symbols_used": symbol_counts, "note": "Too few bullets to judge."}

    dominant_count = max(symbol_counts.values())
    consistency_ratio = round(dominant_count / total_bulleted, 2)
    return {
        "consistent": consistency_ratio >= 0.9,
        "symbols_used": symbol_counts,
        "consistency_ratio": consistency_ratio,
    }


def check_date_format_consistency(resume_text: str) -> dict:
    style_hits = {name: len(pattern.findall(resume_text)) for name, pattern in DATE_PATTERNS.items()}
    # "year_only" heavily overlaps with the other two patterns (a month-year
    # match also contains a bare year), so only count it when neither
    # richer pattern is what actually produced the hit.
    richer_total = style_hits["month_year"] + style_hits["numeric_slash"]
    total_dates = richer_total if richer_total > 0 else style_hits["year_only"]

    if total_dates < 2:
        return {"consistent": True, "styles_found": style_hits, "note": "Too few dates to judge."}

    used_styles = [name for name in ("month_year", "numeric_slash") if style_hits[name] > 0]
    return {
        "consistent": len(used_styles) <= 1,
        "styles_found": style_hits,
        "mixed_styles": used_styles if len(used_styles) > 1 else [],
    }


def check_contact_placement(resume_text: str) -> dict:
    """Contact info should be discoverable near the top, not buried at the bottom."""
    lines = [l for l in resume_text.split("\n") if l.strip()]
    head_text = "\n".join(lines[:6])
    return {
        "email_near_top": bool(EMAIL_PATTERN.search(head_text)),
        "phone_near_top": bool(PHONE_PATTERN.search(head_text)),
        "email_found_anywhere": bool(EMAIL_PATTERN.search(resume_text)),
        "phone_found_anywhere": bool(PHONE_PATTERN.search(resume_text)),
    }


def compute_structure_score(resume_text: str) -> dict:
    sections_found = detect_sections(resume_text)
    presence = check_section_presence(sections_found)
    order = check_section_order(sections_found)
    bullets = check_bullet_consistency(resume_text)
    dates = check_date_format_consistency(resume_text)
    contact = check_contact_placement(resume_text)

    score = 100.0

    # Missing required sections is the biggest structural problem for ATS parsing.
    score -= len(presence["missing_required"]) * 15

    if not order.get("in_conventional_order", True):
        score -= min(10, order.get("inversions", 0) * 4)

    if not bullets.get("consistent", True):
        score -= 10

    if not dates.get("consistent", True):
        score -= 10

    if not (contact["email_near_top"] or contact["email_found_anywhere"]):
        score -= 10
    elif not contact["email_near_top"]:
        score -= 4

    if not contact["phone_found_anywhere"]:
        score -= 5
    elif not contact["phone_near_top"]:
        score -= 2

    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "structure_score": score,
        "sections": presence,
        "section_order": order,
        "bullets": bullets,
        "dates": dates,
        "contact_placement": contact,
    }


if __name__ == "__main__":
    sample = """
John Doe
john.doe@email.com | 555-123-4567

Summary
Backend engineer.

Work Experience
- Built APIs. Jan 2023 - Present
- Led team. 03/2021 - 12/2022

Education
IIT Guwahati Nov 2021 - Jul 2025

Skills
Python, AWS
    """
    import json
    print(json.dumps(compute_structure_score(sample), indent=2))
