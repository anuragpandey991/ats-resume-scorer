"""
experience_matcher.py
Extracts required experience (years) from the JD, and estimates the candidate's
total experience from date ranges found in the resume's WORK EXPERIENCE section
specifically — not the whole document.

Bug this fixes: a naive whole-document date-range scan will pick up education
date ranges too (e.g. "Nov 2021 - Jul 2025" under an "Education" header), wildly
overcounting experience. Verified against a real resume where this inflated the
estimate from ~1.2 years (actual) to ~4.8 years (wrong, because a 3.7-year
degree date range got counted as work experience).
"""

import re
from datetime import datetime

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# All section headers we know how to recognize, so we can tell where the
# "work experience" block ends and the next section (Education, Projects,
# Skills, etc.) begins.
SECTION_HEADERS = {
    "education", "work experience", "experience", "professional experience",
    "employment history", "employment", "internship", "internships",
    "projects", "project experience", "skills", "technical skills",
    "core skills", "certifications", "achievements", "awards",
    "publications", "extracurricular", "activities", "summary", "objective",
    "about", "profile", "leadership", "volunteering", "coursework",
}

# Headers that specifically mark the start of the WORK experience block.
EXPERIENCE_SECTION_HEADERS = {
    "work experience", "experience", "professional experience",
    "employment history", "employment",
}


def _normalize_header_line(line: str) -> str:
    """Strip bullets/punctuation so 'Work Experience:' or '• Experience' still matches a header."""
    return re.sub(r"[^a-z\s]", "", line.strip().lower()).strip()


def extract_work_experience_text(resume_text: str) -> str:
    """
    Return only the text between a "Work Experience"-type header and the next
    (different) section header. Falls back to the full text if no clear
    experience header is found — better to risk over-counting on unusually
    formatted resumes than to return nothing.
    """
    lines = resume_text.split("\n")
    header_hits = [(i, _normalize_header_line(l)) for i, l in enumerate(lines)]
    header_hits = [(i, h) for i, h in header_hits if h in SECTION_HEADERS]

    start_idx = None
    for i, header in header_hits:
        if header in EXPERIENCE_SECTION_HEADERS:
            start_idx = i
            break

    if start_idx is None:
        return resume_text  # no clear header found — safest fallback is "don't guess, use everything"

    end_idx = len(lines)
    for i, header in header_hits:
        if i > start_idx and header not in EXPERIENCE_SECTION_HEADERS:
            end_idx = i
            break

    return "\n".join(lines[start_idx:end_idx])


def extract_required_experience(jd_text: str) -> float | None:
    text = jd_text.lower()

    range_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*\+?\s*years?", text)
    if range_match:
        return float(range_match.group(1))

    plus_match = re.search(r"(\d+)\s*\+\s*years?", text)
    if plus_match:
        return float(plus_match.group(1))

    min_match = re.search(r"(?:minimum(?:\s+of)?|at least)\s*(\d+)\s*years?", text)
    if min_match:
        return float(min_match.group(1))

    plain_match = re.search(r"(\d+)\s*years?\s*(?:of\s*)?experience", text)
    if plain_match:
        return float(plain_match.group(1))

    return None


def _parse_date_token(token: str, default_day: int = 1) -> datetime | None:
    token = token.strip().lower()

    if token in ("present", "current", "now", "till date", "ongoing"):
        return datetime.today()

    m = re.match(r"([a-zA-Z]+)\.?\s+(\d{4})", token)
    if m and m.group(1) in MONTHS:
        return datetime(int(m.group(2)), MONTHS[m.group(1)], default_day)

    m = re.match(r"(\d{1,2})[/-](\d{4})", token)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            return datetime(int(m.group(2)), month, default_day)

    m = re.match(r"(\d{4})", token)
    if m:
        return datetime(int(m.group(1)), 1, default_day)

    return None


def extract_experience_ranges(resume_text: str) -> list:
    month_names = "|".join(sorted(MONTHS.keys(), key=len, reverse=True))
    date_token = rf"(?:(?:{month_names})\.?\s+\d{{4}}|\d{{1,2}}[/-]\d{{4}}|\d{{4}})"

    pattern = re.compile(
        rf"\b({date_token})\s*(?:-|–|—|to)\s*({date_token}|present|current|now)\b",
        re.IGNORECASE,
    )

    ranges = []
    for match in pattern.finditer(resume_text):
        start = _parse_date_token(match.group(1))
        end = _parse_date_token(match.group(2))
        if start and end and end >= start:
            ranges.append((start, end))
    return ranges


def _merge_overlapping_ranges(ranges: list) -> list:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged = [sorted_ranges[0]]
    for current_start, current_end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if current_start <= last_end:
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))
    return merged


def estimate_candidate_experience(resume_text: str) -> float:
    """
    Estimate total years of experience from date ranges found ONLY within the
    resume's work-experience section (see extract_work_experience_text) —
    excludes education, projects, and other non-work date ranges.
    """
    work_text = extract_work_experience_text(resume_text)
    ranges = extract_experience_ranges(work_text)
    merged = _merge_overlapping_ranges(ranges)
    total_days = sum((end - start).days for start, end in merged)
    return round(total_days / 365.25, 1)


def compute_experience_match(jd_text: str, resume_text: str) -> dict:
    required_years = extract_required_experience(jd_text)
    candidate_years = estimate_candidate_experience(resume_text)

    if required_years is None:
        return {
            "required_years": None, "candidate_years": candidate_years,
            "meets_requirement": None, "gap_years": None,
        }

    gap = round(required_years - candidate_years, 1)
    return {
        "required_years": required_years,
        "candidate_years": candidate_years,
        "meets_requirement": candidate_years >= required_years,
        "gap_years": max(0.0, gap),
    }


if __name__ == "__main__":
    jd_sample = "We are looking for a backend engineer with 4+ years of experience in Python and cloud systems."
    resume_sample = """
Education
Indian Institute of Technology, Guwahati Nov 2021 - Jul 2025
Bachelor of Technology - CGPA 8.13

Work Experience
Software Engineer, TechCorp
Jan 2024 - Present
Built backend services in Python.

Skills
Python, AWS, Docker
    """
    print("Required:", extract_required_experience(jd_sample))
    print("Work-experience-section text:", repr(extract_work_experience_text(resume_sample)))
    print("Estimated candidate years:", estimate_candidate_experience(resume_sample))
    print("Full result:", compute_experience_match(jd_sample, resume_sample))
