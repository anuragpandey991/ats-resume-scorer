"""
experience_matcher.py
Extracts required experience (years) from the JD, and estimates the candidate's
total experience from date ranges found in the resume. Compares the two.
"""

import re
from datetime import datetime

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def extract_required_experience(jd_text: str) -> float | None:
    """
    Find the required years of experience mentioned in the JD.
    Handles phrasings like: '5+ years', '3-5 years', 'minimum 2 years',
    'at least 4 years of experience'.
    Returns the LOWEST number mentioned (the minimum bar to clear), or None
    if no such phrase is found.
    """
    text = jd_text.lower()

    # Pattern 1: ranges like "3-5 years" or "3 to 5 years" -> take the lower bound
    range_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*\+?\s*years?", text)
    if range_match:
        return float(range_match.group(1))

    # Pattern 2: "5+ years" or "5 + years"
    plus_match = re.search(r"(\d+)\s*\+\s*years?", text)
    if plus_match:
        return float(plus_match.group(1))

    # Pattern 3: "minimum of 4 years", "at least 4 years", "minimum 4 years"
    min_match = re.search(r"(?:minimum(?:\s+of)?|at least)\s*(\d+)\s*years?", text)
    if min_match:
        return float(min_match.group(1))

    # Pattern 4: plain "4 years of experience"
    plain_match = re.search(r"(\d+)\s*years?\s*(?:of\s*)?experience", text)
    if plain_match:
        return float(plain_match.group(1))

    return None


def _parse_date_token(token: str, default_day: int = 1) -> datetime | None:
    """Parse a single date-like token, e.g. 'Jan 2020', '2020', '01/2020'."""
    token = token.strip().lower()

    if token in ("present", "current", "now", "till date", "ongoing"):
        return datetime.today()

    # "Jan 2020" or "January 2020"
    m = re.match(r"([a-zA-Z]+)\.?\s+(\d{4})", token)
    if m and m.group(1) in MONTHS:
        return datetime(int(m.group(2)), MONTHS[m.group(1)], default_day)

    # "01/2020" or "1-2020"
    m = re.match(r"(\d{1,2})[/-](\d{4})", token)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            return datetime(int(m.group(2)), month, default_day)

    # Just a year: "2020"
    m = re.match(r"(\d{4})", token)
    if m:
        return datetime(int(m.group(1)), 1, default_day)

    return None


def extract_experience_ranges(resume_text: str) -> list:
    """
    Find date ranges in the resume text, e.g. 'Jan 2019 - Mar 2022',
    '2018-2021', 'June 2020 – Present'. Returns a list of (start, end) datetime tuples.
    """
    # Build an alternation of actual month names only (e.g. "jan|january|feb|...")
    # so we never accidentally swallow preceding words like a company name.
    month_names = "|".join(sorted(MONTHS.keys(), key=len, reverse=True))

    # A single date token is one of:
    #   - a real month name + year, e.g. "Jan 2020" / "January 2020"
    #   - numeric month/year, e.g. "01/2020" or "01-2020"
    #   - a bare 4-digit year, e.g. "2020"
    date_token = rf"(?:(?:{month_names})\.?\s+\d{{4}}|\d{{1,2}}[/-]\d{{4}}|\d{{4}})"

    # Matches: <date> <dash-like separator> <date-or-present>, with a word
    # boundary before the first token so we don't start mid-word.
    pattern = re.compile(
        rf"\b({date_token})\s*(?:-|–|—|to)\s*({date_token}|present|current|now)\b",
        re.IGNORECASE,
    )

    ranges = []
    for match in pattern.finditer(resume_text):
        start_raw, end_raw = match.group(1), match.group(2)
        start = _parse_date_token(start_raw)
        end = _parse_date_token(end_raw)
        if start and end and end >= start:
            ranges.append((start, end))
    return ranges


def _merge_overlapping_ranges(ranges: list) -> list:
    """
    Merge overlapping/adjacent date ranges before summing duration, so overlapping
    jobs (or a range mentioned twice) aren't double-counted.
    """
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged = [sorted_ranges[0]]

    for current_start, current_end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if current_start <= last_end:  # overlaps or touches the previous range
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))
    return merged


def estimate_candidate_experience(resume_text: str) -> float:
    """
    Estimate total years of experience by summing merged date ranges found
    in the resume. Returns years rounded to 1 decimal place.
    """
    ranges = extract_experience_ranges(resume_text)
    merged = _merge_overlapping_ranges(ranges)

    total_days = sum((end - start).days for start, end in merged)
    total_years = round(total_days / 365.25, 1)
    return total_years


def compute_experience_match(jd_text: str, resume_text: str) -> dict:
    """
    Combine required vs estimated experience into a single result dict,
    consistent in shape with the other scoring modules.
    """
    required_years = extract_required_experience(jd_text)
    candidate_years = estimate_candidate_experience(resume_text)

    if required_years is None:
        return {
            "required_years": None,
            "candidate_years": candidate_years,
            "meets_requirement": None,
            "gap_years": None,
        }

    gap = round(required_years - candidate_years, 1)
    meets = candidate_years >= required_years

    return {
        "required_years": required_years,
        "candidate_years": candidate_years,
        "meets_requirement": meets,
        "gap_years": max(0.0, gap),
    }


if __name__ == "__main__":
    jd_sample = "We are looking for a backend engineer with 4+ years of experience in Python and cloud systems."
    resume_sample = """
    Software Engineer, TechCorp
    Jan 2021 - Present
    Built backend services in Python.

    Junior Developer, StartupXYZ
    June 2019 - Dec 2020
    Worked on internal tools.
    """

    print("Required experience:", extract_required_experience(jd_sample))
    print("Date ranges found:", extract_experience_ranges(resume_sample))
    print("Estimated candidate experience:", estimate_candidate_experience(resume_sample))
    print("Full result:", compute_experience_match(jd_sample, resume_sample))
