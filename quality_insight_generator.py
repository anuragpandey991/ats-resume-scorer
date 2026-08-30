"""
quality_insight_generator.py
Converts the resume_quality.py report into plain-English, actionable feedback —
separate from the JD-match insights, since these issues exist regardless of
which job you're applying to.
"""


def generate_quality_insights(report: dict) -> list:
    insights = []

    # 1. Contact info — a missing email/phone can get a resume auto-rejected
    # by real ATS systems before a human ever sees it, so this comes first.
    contact = report.get("contact_info", {})
    if not contact.get("has_email"):
        insights.append(
            "No email address detected. Make sure your contact info is in plain text "
            "(not inside an image or text box), or ATS systems may fail to extract it entirely."
        )
    if not contact.get("has_phone"):
        insights.append(
            "No phone number detected. Same risk as above — ensure it's in plain, selectable text."
        )

    # 2. Weak/passive language
    weak_bullets = report.get("weak_language_bullets", [])
    if weak_bullets:
        example = weak_bullets[0]
        insights.append(
            f"Found {len(weak_bullets)} bullet(s) using weak or passive phrasing (e.g. \"responsible for\", "
            f"\"helped with\"). Example: \"{example}\". Rewrite with a strong action verb instead — "
            f"e.g. \"Led\", \"Built\", \"Reduced\", \"Designed\" — to sound more direct and results-driven."
        )

    # 3. Personal pronouns
    pronoun_count = report.get("pronoun_count", 0)
    if pronoun_count > 2:
        insights.append(
            f"Found {pronoun_count} first-person pronouns (I, me, my). Resumes conventionally drop these — "
            f"write \"Led a team of 5\" instead of \"I led a team of 5\"."
        )

    # 4. Quantification — now with specific bullets to fix, not just a percentage
    quant = report.get("quantification", {})
    percent_quantified = quant.get("percent_quantified", 0)
    unquantified = quant.get("unquantified_examples", [])
    if quant.get("total_bullets", 0) > 0 and percent_quantified < 60 and unquantified:
        examples_text = "\n".join(f'  • "{b}" → add a number: how many, how much, or by what %?' for b in unquantified[:3])
        insights.append(
            f"Only {percent_quantified}% of your bullets include a number or metric. "
            f"These specific lines would benefit from a quantified result:\n{examples_text}\n"
            f"Even an approximate figure (\"~30% faster\", \"across 5 markets\") is far more persuasive "
            f"than an unquantified claim, to both recruiters and ATS ranking systems."
        )

    # 5. Length
    length = report.get("length", {})
    if "too short" in length.get("verdict", "") or "too long" in length.get("verdict", ""):
        insights.append(f"Resume length: {length.get('word_count')} words. {length.get('verdict')}")

    # 6. Real grammar issues (LanguageTool) — show several concrete examples,
    # and be transparent about how many technical terms were filtered out so
    # the user trusts the remaining count is real, not tech-term noise.
    grammar = report.get("grammar", {})
    if grammar.get("available"):
        issues = grammar.get("issues", [])
        total_found = grammar.get("total_found", 0)
        filtered = grammar.get("filtered_technical_terms", 0)

        if issues:
            examples = []
            for issue in issues[:5]:
                word = issue.get("flagged_word", "")
                word_part = f' — flagged word: "{word}"' if word else ""
                examples.append(f'  • {issue["category"]}: {issue["message"]}{word_part}')
            examples_text = "\n".join(examples)

            filtered_note = (
                f" ({filtered} additional flags were technical terms and skipped as false positives.)"
                if filtered > 0 else ""
            )
            insights.append(
                f"Grammar/spelling check found {total_found} issue(s) worth reviewing.{filtered_note}\n"
                f"{examples_text}\n"
                f"Review these before submitting — even small slips can hurt credibility with recruiters."
            )
        else:
            filtered_note = f" ({filtered} technical terms were correctly recognized and skipped.)" if filtered > 0 else ""
            insights.append(f"Grammar check found no real issues — well-proofread resume.{filtered_note}")
    # If grammar check was requested but unavailable (no internet, API down),
    # we deliberately say nothing rather than falsely implying grammar was checked.

    # 7. Overall quality verdict
    score = report.get("quality_score", 0)
    if score >= 85:
        insights.append(f"Overall resume quality score: {score}/100 — well-written and ATS-friendly.")
    elif score >= 65:
        insights.append(f"Overall resume quality score: {score}/100 — solid, with a few areas to polish.")
    else:
        insights.append(
            f"Overall resume quality score: {score}/100 — several structural/language issues above "
            f"are worth fixing regardless of which job you apply to."
        )

    return insights


if __name__ == "__main__":
    sample_report = {
        "quality_score": 72.5,
        "weak_language_bullets": ["I was responsible for managing a team of 5 engineers."],
        "passive_voice_matches": [],
        "pronoun_count": 3,
        "quantification": {"percent_quantified": 25.0, "quantified_count": 1, "total_bullets": 4},
        "contact_info": {"has_email": True, "has_phone": False},
        "length": {"word_count": 120, "verdict": "Likely too short — may be missing detail recruiters look for."},
        "grammar": {"available": False, "issues": []},
    }
    for line in generate_quality_insights(sample_report):
        print("-", line)
