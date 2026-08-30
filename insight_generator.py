"""
insight_generator.py
Turns raw score/keyword-match data into plain-English, actionable suggestions
for the candidate.
"""


def generate_insights(keyword_result: dict, semantic_result: dict, final_result: dict,
                       experience_result: dict | None = None) -> list:
    """
    Build a prioritized list of actionable insight strings.
    Order: missing skills -> experience gap -> semantic gap -> overall verdict advice.
    """
    insights = []

    missing = keyword_result.get("missing_skills", [])
    matched = keyword_result.get("matched_skills", [])
    jd_skills = keyword_result.get("jd_skills", [])
    semantic_matched = keyword_result.get("semantic_matched_skills", [])

    # 1. Missing skills — the single most actionable feedback
    if missing:
        skill_list = ", ".join(missing[:10])  # cap length for readability
        insights.append(
            f"Your resume is missing {len(missing)} skill(s) mentioned in the job description: "
            f"{skill_list}. Add these explicitly if you have genuine experience with them — "
            f"ATS systems scan for exact keyword matches."
        )
    elif jd_skills:
        insights.append(
            "Great news — your resume already covers all the key skills detected in this job description."
        )

    # 1b. Experience gap — placed early since it's a hard, factual gap the
    # candidate can't argue around, similar in weight to missing skills.
    if experience_result and experience_result.get("required_years") is not None:
        required = experience_result["required_years"]
        candidate = experience_result["candidate_years"]
        gap = experience_result.get("gap_years", 0.0)

        if experience_result.get("meets_requirement"):
            insights.append(
                f"Experience requirement met: this role asks for {required}+ years, and your resume "
                f"shows approximately {candidate} years based on the date ranges found."
            )
        else:
            insights.append(
                f"This role asks for {required}+ years of experience, but your resume shows approximately "
                f"{candidate} years based on the date ranges found — a gap of about {gap} year(s). "
                f"If you have relevant experience not reflected in clear date ranges (e.g. project work, "
                f"contract roles), make sure it's dated clearly so it's counted."
            )

    # 2. Keyword match percentage context
    kw_percent = keyword_result.get("match_percent", 0)
    if jd_skills and kw_percent < 50:
        insights.append(
            f"Only {kw_percent}% of the JD's key skills appear in your resume. "
            f"Consider tailoring your resume specifically for this role rather than using a generic version."
        )

    # 3. Semantic similarity feedback
    sem_percent = semantic_result.get("similarity_percent", 0)
    if sem_percent < 50:
        insights.append(
            "Your resume's overall language and experience descriptions don't closely align with this "
            "job description's context. Try mirroring the JD's terminology and responsibilities more "
            "closely in your bullet points (e.g. if JD says 'led cross-functional teams', use similar phrasing "
            "if that reflects your experience)."
        )
    elif 50 <= sem_percent < 70:
        insights.append(
            "Your resume is contextually related to this role but could be phrased more closely to the "
            "JD's language in a few sections to strengthen the match."
        )

    # 4. Matched skills — positive reinforcement (candidates want to know what's working too)
    if matched:
        insights.append(
            f"Skills you've correctly highlighted that match this JD: {', '.join(matched[:10])}."
        )

    if semantic_matched:
        insights.append(
            f"Note: {', '.join(semantic_matched)} weren't stated as exact keywords, but your resume's "
            f"content implies them strongly enough to count. Consider stating them explicitly anyway — "
            f"real ATS systems often only scan for literal keywords, not inferred meaning."
        )

    # 5. Overall verdict-based closing advice
    verdict = final_result.get("verdict", "")
    final_score = final_result.get("final_score", 0)
    if verdict == "Poor Match":
        insights.append(
            f"Overall score: {final_score}/100. This resume likely needs significant tailoring, or this "
            f"role may not align well with your current experience — review the missing skills above first."
        )
    elif verdict == "Weak Match":
        insights.append(
            f"Overall score: {final_score}/100. A few targeted edits (adding missing keywords, "
            f"aligning phrasing) could meaningfully improve your match rate."
        )
    elif verdict == "Moderate Match":
        insights.append(
            f"Overall score: {final_score}/100. You're a reasonable fit — polishing keyword coverage "
            f"could push this into a strong match."
        )
    else:  # Strong Match
        insights.append(
            f"Overall score: {final_score}/100. Strong alignment with this job description."
        )

    return insights


if __name__ == "__main__":
    kw_result = {
        "match_percent": 50.0,
        "jd_skills": ["AWS", "Django", "Docker", "PostgreSQL", "Python", "React"],
        "matched_skills": ["AWS", "Docker", "Python"],
        "missing_skills": ["Django", "PostgreSQL", "React"],
    }
    sem_result = {"similarity_percent": 62.0}
    final_result = {"final_score": 55.4, "verdict": "Moderate Match"}
    exp_result = {"required_years": 5.0, "candidate_years": 3.2, "meets_requirement": False, "gap_years": 1.8}

    for line in generate_insights(kw_result, sem_result, final_result, exp_result):
        print("-", line)
