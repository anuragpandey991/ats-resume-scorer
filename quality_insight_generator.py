"""
quality_insight_generator.py
Converts the resume_quality.py report into strengths + improvements, same
structure as insight_generator.py, for a consistent tone across both sections.
"""


def generate_quality_insights(report: dict) -> dict:
    strengths = []
    improvements = []

    contact = report.get("contact_info", {})
    if contact.get("has_email") and contact.get("has_phone"):
        strengths.append("Contact info (email and phone) is present and detectable.")
    if not contact.get("has_email"):
        improvements.append(
            "No email address detected. Make sure it's in plain text (not an image/text box), "
            "or ATS systems may fail to extract it entirely."
        )
    if not contact.get("has_phone"):
        improvements.append("No phone number detected. Same risk — ensure it's in plain, selectable text.")

    weak_bullets = report.get("weak_language_bullets", [])
    if weak_bullets:
        example = weak_bullets[0]
        improvements.append(
            f'Found {len(weak_bullets)} bullet(s) using weak phrasing (e.g. "responsible for", "helped with"). '
            f'Example: "{example}". A strong action verb ("Led", "Built", "Reduced") reads more direct and results-driven.'
        )

    pronoun_count = report.get("pronoun_count", 0)
    if pronoun_count > 2:
        improvements.append(
            f"Found {pronoun_count} first-person pronouns (I, me, my). Resumes conventionally drop these — "
            f'write "Led a team of 5" instead of "I led a team of 5".'
        )

    quant = report.get("quantification", {})
    percent_quantified = quant.get("percent_quantified", 0)
    unquantified = quant.get("unquantified_examples", [])
    if quant.get("total_bullets", 0) > 0:
        if percent_quantified >= 60:
            strengths.append(f"{percent_quantified}% of your bullets already include a number or metric — good practice.")
        elif unquantified:
            examples_text = "\n".join(f'  • "{b}"' for b in unquantified[:3])
            improvements.append(
                f"Only {percent_quantified}% of your bullets include a number or metric. These could use one:\n"
                f"{examples_text}\nEven an approximate figure (\"~30% faster\", \"across 5 markets\") is more persuasive than an unquantified claim."
            )

    length = report.get("length", {})
    if "Reasonable" in length.get("verdict", ""):
        pass  # no need to call out something that's simply fine
    else:
        improvements.append(f"Resume length: {length.get('word_count')} words. {length.get('verdict')}")

    grammar = report.get("grammar", {})
    if grammar.get("available"):
        issues = grammar.get("issues", [])
        filtered = grammar.get("filtered_technical_terms", 0)
        if issues:
            examples = []
            for issue in issues[:5]:
                word = issue.get("flagged_word", "")
                word_part = f' — "{word}"' if word else ""
                examples.append(f'  • {issue["category"]}{word_part}: {issue["message"]}')
            examples_text = "\n".join(examples)
            filtered_note = f" ({filtered} technical terms were correctly recognized and skipped.)" if filtered else ""
            improvements.append(
                f"Grammar/spelling check found {len(issues)} issue(s) worth reviewing.{filtered_note}\n{examples_text}"
            )
        else:
            filtered_note = f" ({filtered} technical terms were correctly recognized and skipped.)" if filtered else ""
            strengths.append(f"Grammar check found no real issues — well-proofread resume.{filtered_note}")

    score = report.get("quality_score", 0)
    if score >= 85:
        strengths.append(f"Overall resume quality score: {score}/100 — well-written and ATS-friendly.")
    elif score >= 65:
        strengths.append(f"Overall resume quality score: {score}/100 — solid, with a few areas to polish.")
    else:
        improvements.append(f"Overall resume quality score: {score}/100 — the items above are worth fixing regardless of which job you apply to.")

    return {"strengths": strengths, "improvements": improvements}


if __name__ == "__main__":
    sample_report = {
        "quality_score": 78.8,
        "weak_language_bullets": [],
        "pronoun_count": 0,
        "quantification": {"percent_quantified": 55.3, "quantified_count": 21, "total_bullets": 38, "unquantified_examples": ["Built things without a number."]},
        "contact_info": {"has_email": True, "has_phone": True},
        "length": {"word_count": 420, "verdict": "Reasonable length."},
        "grammar": {"available": True, "issues": [{"category": "Punctuation", "flagged_word": "-", "message": "Consider using an en dash."}], "filtered_technical_terms": 14},
    }
    result = generate_quality_insights(sample_report)
    print("STRENGTHS:")
    for s in result["strengths"]:
        print(" +", s)
    print("\nIMPROVEMENTS:")
    for i in result["improvements"]:
        print(" -", i)
