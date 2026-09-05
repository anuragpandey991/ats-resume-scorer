"""
insight_generator.py
Turns raw score/keyword-match data into plain-English, actionable suggestions.
Structured as strengths-first, then gaps — a candidate who matches most of the
JD's skills and meets the experience bar should see that reflected clearly
before reading about the 1-2 things that are actually missing.
"""


def generate_insights(keyword_result: dict, semantic_result: dict, final_result: dict,
                       experience_result: dict | None = None) -> dict:
    """
    Returns {"strengths": [...], "improvements": [...]} instead of one flat
    list — this is what actually fixes the "sounds too harsh" problem: a
    resume with an 80% skill match and experience met should visibly lead
    with that, not bury it under a "needs work" framing.
    """
    strengths = []
    improvements = []

    missing = keyword_result.get("missing_skills", [])
    matched = keyword_result.get("matched_skills", [])
    jd_skills = keyword_result.get("jd_skills", [])
    semantic_matched = keyword_result.get("semantic_matched_skills", [])
    kw_percent = keyword_result.get("match_percent", 0)

    # --- Strengths first ---
    if matched:
        strengths.append(
            f"You match {len(matched)} of {len(jd_skills)} skills this JD asks for ({kw_percent}%): "
            f"{', '.join(matched[:10])}."
        )

    if experience_result and experience_result.get("required_years") is not None:
        if experience_result.get("meets_requirement"):
            strengths.append(
                f"Experience requirement met: this role asks for {experience_result['required_years']}+ years, "
                f"and your resume shows approximately {experience_result['candidate_years']} years."
            )

    if semantic_matched:
        strengths.append(
            f"{', '.join(semantic_matched)} weren't stated as exact keywords, but your resume's content "
            f"implies them strongly enough to count."
        )

    sem_percent = semantic_result.get("similarity_percent", 0)
    if sem_percent >= 70:
        strengths.append("Your resume's overall language and experience closely mirror this JD's context.")

    # --- Then improvements, phrased proportionally to how close the match already is ---
    if missing:
        skill_list = ", ".join(missing[:10])
        severity = "one last gap" if len(missing) <= 2 and kw_percent >= 70 else f"{len(missing)} skill(s)"
        improvements.append(
            f"Missing {severity} the JD mentions: {skill_list}. Add these explicitly if you have "
            f"genuine experience with them — ATS systems scan for exact keyword matches."
        )
        if semantic_matched:
            improvements.append(
                f"Consider stating {', '.join(semantic_matched)} explicitly too, even though we inferred them — "
                f"real ATS systems often only scan for literal keywords, not inferred meaning."
            )

    if experience_result and experience_result.get("required_years") is not None and not experience_result.get("meets_requirement"):
        improvements.append(
            f"This role asks for {experience_result['required_years']}+ years; your resume shows approximately "
            f"{experience_result['candidate_years']} years — a gap of about {experience_result['gap_years']} year(s)."
        )

    if sem_percent < 50:
        improvements.append(
            "Your resume's specific skills may be there, but the surrounding language differs from this JD's "
            "phrasing. Try mirroring a few more of its terms in your bullet points where genuinely applicable."
        )
    elif 50 <= sem_percent < 70 and kw_percent < 70:
        improvements.append(
            "Your resume is contextually related to this role but could echo the JD's language a bit more "
            "closely in a few sections to strengthen the match."
        )

    structure_percent = final_result.get("breakdown", {}).get("structure_formatting")
    if structure_percent is not None and structure_percent < 70:
        improvements.append(
            f"Structure/formatting score is {structure_percent}/100 — see the Resume Quality tab for "
            f"section, bullet, and date-format details that affect ATS parsing."
        )

    verdict = final_result.get("verdict", "")
    verdict_description = final_result.get("verdict_description", "")
    score = final_result.get("final_score", 0)
    strengths.append(f"Overall: {score}/100 — {verdict}. {verdict_description}")

    return {"strengths": strengths, "improvements": improvements}


if __name__ == "__main__":
    kw_result = {
        "match_percent": 80.0,
        "jd_skills": ["Collaboration", "Communication", "Data Analysis", "Leadership", "Machine Learning", "Rust", "SQL", "Stakeholder Management", "Statistics", "Tableau"],
        "matched_skills": ["Collaboration", "Communication", "Data Analysis", "Leadership", "Machine Learning", "SQL", "Stakeholder Management", "Statistics"],
        "missing_skills": ["Rust", "Tableau"],
        "semantic_matched_skills": ["Communication", "Data Analysis", "Leadership"],
    }
    sem_result = {"similarity_percent": 42.4}
    exp_result = {"required_years": 1.0, "candidate_years": 1.3, "meets_requirement": True, "gap_years": 0.0}
    final_result = {"final_score": 59.3, "verdict": "Developing Fit", "verdict_description": "A reasonable foundation — a handful of targeted edits could meaningfully raise this."}

    result = generate_insights(kw_result, sem_result, final_result, exp_result)
    print("STRENGTHS:")
    for s in result["strengths"]:
        print(" +", s)
    print("\nIMPROVEMENTS:")
    for i in result["improvements"]:
        print(" -", i)
